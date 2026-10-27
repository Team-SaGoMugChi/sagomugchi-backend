"""1'. 제작팀 모드 — 역할을 나눈 여러 번의 LLM 호출로 스토리보드를 만든다(VIDEOMAKE_PLANNER=team).

한 번의 호출(stages/storyboard.py)은 일기 해석·컷 구성·연속성 점검을 한꺼번에 한다. 제작팀 모드는
영화 제작처럼 나눈다.

  1. 작가(story editor)   일기 → 제작 노트: 사건 목록(사실·실제 대사·실제 상황 기준 감정·시간대),
                           인물(성별 포함)·장소·소지품, 마지막 감정. 사실을 빠뜨리거나 지어내지 않게 먼저 못 박는다.
  2. 감독(콘티)           제작 노트 + 기존 규칙 → 스토리보드 초안 (가드레일 재요청 포함, 기존 함수 재사용)
  3. 스크립터(검수)       초안 vs 일기·제작 노트: 빠진 사실, 지어낸 내용, 감정 불일치, 연속성(자리·소지품·
                           시간대·좌우), 마지막 감정 → 고칠 목록. 문제 없으면 승인.
  4. 감독(수정)           고칠 목록만 반영한 수정본. 검수는 최대 REVIEW_ROUNDS번.
  5. 촬영감독             나레이션·무음 컷 일부를 2~3개 샷으로 나눈다(같은 순간의 다른 각도·반응·손과 물건).
                           영상 모델이 한 번 생성으로 컷 전환까지 만든다 — 생성 길이가 같아 비용은 그대로다.
                           대사 컷은 입 모양·목소리를 맞춰야 해서 나누지 않는다. (settings.shot_split)

검수도 같은 LLM(GPT)이 역할만 바꿔 맡는다. 평가 도구의 판정자(Gemini)를 검수에 쓰면 결과가 판정자에
맞춰지므로 일부러 쓰지 않는다. 각 단계 결과는 job/team/에 남는다(제작 회의록).
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from ..config import Settings
from ..errors import GuardrailViolation
from ..handoff import storyboard_context
from ..job import JobStore
from ..models import Cut, DiaryInput, Shot, Storyboard
from ..prompts import PromptLibrary
from ..providers.base import LLMProvider
from .storyboard import _feedback, plan_storyboard

log = logging.getLogger(__name__)

REVIEW_ROUNDS = 2
Mood = Literal["기쁨", "슬픔", "분노", "불안", "상처", "당황", "평온"]


class Beat(BaseModel):
    order: int
    what_happened: str = Field(..., description="일기에 적힌 사실 그대로, 한 문장")
    who: list[str]
    where: str
    time_of_day: str = Field(..., description="아침/낮/저녁/밤 등 일기 근거. 모르면 '알 수 없음'")
    actual_quote: str = Field(..., description="이 사건에서 오간 말(따옴표든 '~라고 했다'든). 전해 들은 말은 뜻 그대로 짧은 직접 대사로 옮긴다. 없으면 빈 문자열")
    emotion: Mood = Field(..., description="문장 분석이 아니라 실제 상황 기준 감정")
    intensity: int = Field(..., ge=0, le=100)
    props: list[str] = Field(..., description="이 순간 인물이 들고 있거나 쓰는 물건")
    must_show: bool = Field(..., description="이게 빠지면 이야기가 이해되지 않는가(원인·전환점)")


class Person(BaseModel):
    name: str
    role: str = Field(..., description="주인공/조연 — 일기 속 관계(친구, 팀장 등)")
    gender: Literal["man", "woman", "boy", "girl"]
    on_screen: bool


class ProductionNotes(BaseModel):
    protagonist_name: str
    people: list[Person]
    places: list[str]
    beats: list[Beat]
    ending_emotion: Mood = Field(..., description="일기 마지막 문장이 말한 감정")
    ending_sentence: str
    tone_warnings: list[str] = Field(..., description="문장 분석 감정이 실제 상황과 다른 곳 등 주의점")


class Issue(BaseModel):
    cut: int = Field(..., description="해당 컷 번호. 전체 문제면 0")
    kind: Literal["빠진 사실", "지어낸 내용", "감정 불일치", "연속성", "마지막 감정", "기타"]
    problem: str
    fix: str


class Review(BaseModel):
    approve: bool
    issues: list[Issue]


class ShotPlanCut(BaseModel):
    cut: int
    shots: list[Shot]


class ShotPlan(BaseModel):
    cuts: list[ShotPlanCut] = Field(..., description="샷을 나눌 컷만. 나누지 않는 컷은 넣지 않는다")


WRITER_SYSTEM = """너는 영화 제작팀의 작가(스토리 에디터)다. 사용자의 일기를 3인칭 짧은 영상으로 만들기 전에,
감독과 스크립터가 함께 볼 '제작 노트'를 만든다. 해석하거나 꾸미지 않고 사실을 정리한다.

규칙
- 일기에 적힌 사건만 순서대로 적는다. 지어내지 않는다.
- must_show=true는 이야기의 원인·감정 전환점·결말에만 준다(전체 사건의 절반 이하). 영상은 컷이 10개 이하라
  모든 사건을 담을 수 없다. 나머지는 감독이 합치거나 나레이션으로 지나가게 둔다.
- actual_quote: 일기에 적힌 말을 넣는다. 따옴표로 적힌 말은 그대로, '~라고 했다'처럼 전해 들은 말은
  **뜻을 바꾸지 않고** 그 사람이 했을 짧은 직접 대사로 옮긴다(예: "너무 예민하게 굴지 말라고 했다" →
  "너무 예민하게 굴지 마."). 일기에 말이 없는 사건에는 대사를 만들지 않는다(빈 문자열).
- 감정은 실제 상황으로 판단한다. 아래 '장면 후보'의 감정은 문장 분석이라 틀릴 수 있다
  (예: "팀장이 내 아이디어를 발표했다"가 기쁨으로 잡혀도 실제로는 분노·당황). 다르면 tone_warnings에 적는다.
- props: 그 순간 인물이 들고 있는 물건(우산, 휴대폰, 빵 봉투 등). 다음 사건에도 들고 있으면 거기에도 적는다.
- 사람마다 성별을 정한다. 일기에서 알 수 없으면 하나를 고른다. 화면에 나오지 않고 목소리만 있는 사람은 on_screen=false.
- protagonist_name은 일기 작성자와 겹치지 않는 흔한 한국어 이름(이미 정해졌으면 그 이름).
- ending_emotion·ending_sentence: 일기 마지막 문장이 말한 감정 그대로(지어낸 위로·교훈 금지)."""

REVIEW_SYSTEM = """너는 영화 제작팀의 스크립터(검수자)다. 감독이 만든 스토리보드 초안을 일기와 제작 노트에 비추어
검수한다. 직접 고치지 않고 고칠 점만 정확히 짚는다. 연출 취향(카메라 각도 선호 등)은 지적하지 않는다.

확인할 것
1. 빠진 사실: 제작 노트에서 must_show=true인 사건이 컷에 없다.
2. 지어낸 내용: 일기에 없는 인물·장소·사건·대사가 있다. 단, 일기에 '~라고 했다'로 적힌 말을 뜻 그대로
   대사로 옮긴 것은 지어낸 것이 아니다.
3. 감정 불일치: 컷의 mood가 그 사건의 실제 감정(제작 노트)과 다르다.
4. 연속성: 같은 장소·같은 순간의 연속 컷에서 자리·좌우 위치·소지품·시간대(낮/밤)가 어긋나거나,
   들고 있던 물건이 설명 없이 사라진다.
5. 마지막 감정: 마지막 컷의 mood·나레이션이 일기 마지막 감정과 다르거나 없는 위로·교훈을 붙였다.
문제가 없으면 approve=true, issues=[]. 사소한 표현 차이는 문제로 보지 않는다."""


CINEMATOGRAPHER_SYSTEM = """너는 영화 제작팀의 촬영감독이다. 확정된 스토리보드를 받아, 일부 컷을 드라마처럼 2~3개의
샷으로 나눈다. 영상 모델은 컷 하나를 한 번에 만들면서 지정한 시각에 컷을 전환한다.

나눌 컷 고르기
- 나레이션 컷이나 무음 컷 중, 한 순간을 여러 각도로 보여주면 더 잘 전달되는 컷(감정이 드러나는 순간,
  두 사람 이상이 있는 장면, 물건이 중요한 장면). 길이 6초 이상인 컷만. 전체 컷의 절반 이하.
- 대사 컷은 나누지 않는다(넣지 않는다).

샷 규칙
- 샷 2~3개, 각 1.5초 이상, 합은 그 컷의 duration_seconds와 정확히 같다.
- 첫 샷은 컷 그림(image_prompt) 그대로다. framing은 컷의 camera_distance와 같게, view는 image_prompt를 짧게 요약.
- 다음 샷은 **같은 장소·같은 순간**을 다르게 본다: 반대편 각도, 다른 인물의 반응, 손이나 물건(insert).
  화면에 나오는 사람은 그 컷의 cast에 있는 사람만이다. 새 사람·새 장소·새 사건을 만들지 않는다.
- 반대편·반응 샷에서도 사람마다 화면 좌우는 첫 샷과 같다(180도 선을 넘지 않는다). 옷차림·소지품도 같다.
- insert가 아닌 샷에서는 사람의 머리와 얼굴 전체가 화면 안에 있다(얼굴을 자르고 몸통만 보이는 샷 금지).
- 거리두기: framing은 wide / full / medium / insert만. 얼굴이 화면을 채우는 클로즈업, 1인칭 시점은
  쓰지 않는다(어깨너머 샷은 된다: 앞에 걸친 어깨는 상대방이다). insert는 손·물건만 가깝게, 얼굴은 나오지 않는다.
- 샷마다 동작은 한 방향으로 한 번만이다. 물건을 주고받거나 밀었다 당기는 동작을 쓰지 않는다(영상 모델이
  줬다 가져갔다를 반복한다). insert는 그 순간의 상태를 보여준다: 예 "the owner's wrinkled hand resting over
  Jieun's hand". 눈물이 흐르는 모습은 쓰지 않는다("eyes look moist, holding back tears"까지만).
- 뒤 샷은 앞 샷과 같은 순간이다. 반응·어깨너머 샷에서 새 동작을 시작하지 않는다(손·물건은 그 자리에 그대로).
- insert의 view에는 손이 첫 샷에서 어디에 있는지("held in the air between them at waist height",
  "resting on the green counter")를 그대로 쓴다. 첫 샷에 없는 탁자·진열대 위로 손을 옮기지 않는다.
- view(영어)에는 카메라 위치, 보이는 사람(외모로 가리킴: 예 "the woman in the beige blazer"), 그리고
  **사람마다 어디를 보는지**(다른 사람·물건·창밖 등)를 반드시 쓴다. 아무도 카메라를 보지 않는다.
- 표정·자세는 그 컷의 mood와 같다. 같은 옷, 같은 빛, 같은 시간대."""


def _shot_brief(sb: Storyboard) -> str:
    people = {c.name: c.appearance.split(".")[0] for c in sb.characters}
    cuts = []
    for c in sb.cuts:
        cuts.append({"cut": c.index, "duration_seconds": c.duration_seconds, "camera_distance": c.camera_distance,
                     "mood": c.mood, "location": c.location, "cast": [m.name for m in c.cast],
                     "voice": "dialogue" if c.dialogue else ("narration" if c.narration else "silent"),
                     "narration": c.narration, "image_prompt": c.image_prompt, "motion_prompt": c.motion_prompt})
    return (f"## 인물 외모\n{json.dumps(people, ensure_ascii=False, indent=1)}\n\n"
            f"## 스토리보드\n{json.dumps(cuts, ensure_ascii=False, indent=1)}")


def apply_shot_plan(sb: Storyboard, plan: ShotPlan) -> tuple[Storyboard, list[str]]:
    """샷 계획을 컷에 붙인다. 규칙에 맞지 않는 컷은 한 샷으로 둔다. (스토리보드, 버린 이유들)"""
    cuts, dropped = list(sb.cuts), []
    by_index = {c.index: i for i, c in enumerate(cuts)}
    for item in plan.cuts:
        i = by_index.get(item.cut)
        if i is None:
            dropped.append(f"컷 {item.cut}: 없는 컷")
            continue
        cut = cuts[i]
        if cut.dialogue or cut.duration_seconds < 6:
            dropped.append(f"컷 {item.cut}: 대사 컷이거나 6초 미만")
            continue
        shots = list(item.shots)
        if shots:
            shots[0] = shots[0].model_copy(update={"framing": cut.camera_distance})
        try:
            cuts[i] = Cut.model_validate({**cut.model_dump(), "shots": [s.model_dump() for s in shots]})
        except ValueError as exc:
            dropped.append(f"컷 {item.cut}: {str(exc).splitlines()[-1][:80]}")
    return sb.model_copy(update={"cuts": cuts}), dropped


async def plan_shots(sb: Storyboard, *, llm: LLMProvider, job: JobStore | None = None) -> Storyboard:
    try:
        plan, meta = await llm.complete_json(system=CINEMATOGRAPHER_SYSTEM, user=_shot_brief(sb), schema=ShotPlan)
    except Exception as exc:  # 샷 나누기는 덧붙이는 단계다. 실패해도 스토리보드는 그대로 쓴다.
        log.warning("제작팀 촬영감독 실패 — 샷을 나누지 않는다: %s", exc)
        return sb
    if job:
        job.record_cost("team cinematographer", meta.cost_usd)
    out, dropped = apply_shot_plan(sb, plan)
    if job:
        (job.dir / "team" / "5_cinematographer.json").write_text(
            json.dumps({"plan": plan.model_dump(), "dropped": dropped}, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("제작팀 촬영감독: 샷을 나눈 컷 %s, 버림 %s",
             [c.index for c in out.cuts if c.shots], dropped)
    return out


def _notes_text(notes: ProductionNotes) -> str:
    lines = ["\n\n## 제작 노트 (작가실에서 정리 — 사실·감정·연속성의 기준)\n",
             f"주인공 이름: {notes.protagonist_name}"]
    for p in notes.people:
        lines.append(f"- 인물 {p.name} ({p.role}, {p.gender}{'' if p.on_screen else ', 화면 밖 목소리'})")
    lines.append("장소: " + ", ".join(notes.places))
    lines.append("\n사건 (순서대로 — must_show는 반드시 컷에 담는다)")
    for b in notes.beats:
        q = f' / 일기 속 말: "{b.actual_quote}"' if b.actual_quote else ""
        props = f" / 소지품: {', '.join(b.props)}" if b.props else ""
        lines.append(f"{b.order}. [{b.emotion} {b.intensity}{' · must_show' if b.must_show else ''}] {b.what_happened}"
                     f" — {', '.join(b.who)} @ {b.where}, {b.time_of_day}{q}{props}")
    lines.append(f"\n마지막 감정: {notes.ending_emotion} — \"{notes.ending_sentence}\"")
    if notes.tone_warnings:
        lines.append("주의: " + " / ".join(notes.tone_warnings))
    if any(b.actual_quote and b.must_show for b in notes.beats):
        lines.append("일기 속 말이 사건의 전환점(must_show)이면 그 말을 dialogue 컷으로 보여준다(문장은 일기 속 말 그대로).")
    lines.append("\n위 제작 노트를 따라 스토리보드를 만든다. 제작 노트의 감정이 '장면 후보'의 감정과 다르면 제작 노트를 따른다.")
    return "\n".join(lines)


async def plan_with_team(
    diary: DiaryInput,
    *,
    llm: LLMProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore | None = None,
) -> Storyboard:
    team_dir = job.dir / "team" if job else None
    if team_dir:
        team_dir.mkdir(exist_ok=True)

    # 1. 작가
    ctx = storyboard_context(diary.handoff)
    writer_user = (
        f"## 일기\n\n{diary.text}\n\n## 감정분석 결과\n\n{json.dumps(diary.emotion, ensure_ascii=False)}"
        + (f"\n\n## 장면 후보·대화 칸 (문장 분석 — 틀릴 수 있음)\n\n{json.dumps(ctx, ensure_ascii=False, indent=1)}" if ctx else "")
        + (f"\n\n주인공 이름은 \"{diary.protagonist_name}\"로 정해져 있다." if diary.protagonist_name else "")
    )
    notes, meta = await llm.complete_json(system=WRITER_SYSTEM, user=writer_user, schema=ProductionNotes)
    if job:
        job.record_cost("team writer", meta.cost_usd)
    if team_dir:
        (team_dir / "1_writer_notes.json").write_text(notes.model_dump_json(indent=1), encoding="utf-8")
    log.info("제작팀 작가: 사건 %d개, 마지막 감정 %s", len(notes.beats), notes.ending_emotion)

    # 2. 감독 초안 (이름은 작가가 정한 것으로 고정)
    directed = diary.model_copy(update={"protagonist_name": diary.protagonist_name or notes.protagonist_name})
    extra = _notes_text(notes)
    sb = await plan_storyboard(directed, llm=llm, prompts=prompts, settings=settings, job=None, extra=extra)
    if team_dir:
        (team_dir / "2_director_draft.json").write_text(sb.model_dump_json(indent=1), encoding="utf-8")

    # 3·4. 스크립터 검수 → 감독 수정
    for rnd in range(1, REVIEW_ROUNDS + 1):
        review_user = (
            f"## 일기\n\n{diary.text}{extra}\n\n## 스토리보드 초안\n\n{sb.model_dump_json(indent=1)}"
        )
        review, meta = await llm.complete_json(system=REVIEW_SYSTEM, user=review_user, schema=Review)
        if job:
            job.record_cost(f"team review {rnd}", meta.cost_usd)
        if team_dir:
            (team_dir / f"3_review_{rnd}.json").write_text(review.model_dump_json(indent=1), encoding="utf-8")
        log.info("제작팀 검수 %d: 승인=%s, 지적 %d건", rnd, review.approve, len(review.issues))
        if review.approve or not review.issues:
            break
        issues = [f"[{i.kind}] 컷 {i.cut}: {i.problem} → {i.fix}" for i in review.issues]
        try:
            sb = await plan_storyboard(
                directed, llm=llm, prompts=prompts, settings=settings, job=None, extra=extra,
                initial_feedback=_feedback(issues, sb.model_dump_json()),
            )
        except GuardrailViolation as exc:
            # 수정본이 연출 규칙을 못 지키면 규칙을 지킨 직전 초안을 쓴다(전체를 버리지 않는다).
            log.warning("제작팀 수정 %d이 규칙 검사를 통과하지 못해 직전 초안을 유지: %s", rnd, exc)
            break
        if team_dir:
            (team_dir / f"4_director_revision_{rnd}.json").write_text(sb.model_dump_json(indent=1), encoding="utf-8")

    # 5. 촬영감독
    if settings.shot_split:
        sb = await plan_shots(sb, llm=llm, job=job)

    if job:
        job.save_storyboard(sb)
    return sb
