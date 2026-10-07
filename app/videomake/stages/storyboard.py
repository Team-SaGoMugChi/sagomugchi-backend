"""1. StoryboardPlanner — 일기 + 감정분석 → N컷 스토리보드.

LLM 출력을 그대로 믿지 않는다. 가드레일 린터를 통과할 때까지 위반 내역을
피드백으로 넣어 재요청한다. LLM 호출은 컷당 1센트 미만이고 영상은 컷당 $0.80이므로,
여기서 반복하는 비용은 사실상 0이다.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from ..config import (
    CROSSFADE_SECONDS,
    CUT_DURATIONS,
    MAX_SILENT_RUN,
    SILENT_CUT_SECONDS,
    DIALOGUE_MAX_LINES,
    DIALOGUE_MIN_LINES,
    DIALOGUE_MIN_SECONDS,
    CutSeconds,
    Settings,
    dialogue_max_chars,
    narration_chars_for_window,
    narration_max_chars,
)
from ..errors import GuardrailViolation
from ..guardrails import lint_storyboard
from ..handoff import storyboard_context
from ..job import JobStore
from ..models import (
    CharacterProfile,
    Cut,
    CutMood,
    DiaryInput,
    Distortion,
    LocationProfile,
    Line,
    Stage,
    Storyboard,
)
from ..prompts import PromptLibrary
from ..providers.base import LLMProvider

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
# 전체 길이가 상한에서 이만큼 안쪽이면 "상한 근처"로 보고 늘어진 컷을 줄이게 한다.
NEAR_CAP_SECONDS = 4


def _feedback(violations: list[str], previous_json: str) -> str:
    """재요청 피드백. 직전 결과를 함께 준다.

    위반 목록만 주면 LLM이 스토리보드를 처음부터 다시 써서, 지적된 곳은 고치지만
    다른 곳에서 새 위반을 만든다(GPT에서 실제로 관측됨). 직전 결과를 주고 위반만
    고치게 해야 수렴한다.
    """
    return (
        "\n\n## 직전 결과\n\n"
        + previous_json
        + "\n\n## 직전 결과의 연출 원칙 위반\n\n"
        + "\n".join(f"- {v}" for v in violations)
        + "\n\n직전 결과에서 위 항목만 고쳐라. 위반이 없는 부분은 그대로 둔다."
    )


class _LineDraft(BaseModel):
    speaker: str
    text: str


class _CutDraft(BaseModel):
    """LLM 출력용 스키마. 길이 위반을 예외가 아니라 린터 피드백으로 다루기 위해
    Cut의 엄격한 validator를 뺀 사본이다."""

    index: int
    image_prompt: str
    motion_prompt: str
    # 컷마다 둘 중 하나만 채운다. 빈 문자열/빈 배열이 "안 씀"을 뜻한다.
    # Optional 타입을 쓰면 구조화 출력 스키마가 nullable이 되어 LLM이 헷갈린다.
    narration: str
    dialogue: list[_LineDraft]
    camera_distance: Literal["wide", "full", "medium"]
    # 컷마다 LLM이 장면에 필요한 만큼 고른다. Veo는 4·6·8초만 만든다.
    duration_seconds: CutSeconds
    # 그 컷이 담은 장면의 감정. 빛·색감·표정이 따라간다.
    mood: CutMood
    # locations에 정의한 장소 이름. 같은 장소의 컷은 같은 곳으로 그려진다.
    location: str


class _StoryboardDraft(BaseModel):
    protagonist: CharacterProfile
    supporting: list[CharacterProfile] = Field(default_factory=list)
    distortions: list[Distortion] = Field(default_factory=list)
    locations: list[LocationProfile]
    cuts: list[_CutDraft]

    def cut_errors(self) -> list[str]:
        """컷별 규칙 위반을 전부 모은다. 각 항목에 컷 번호를 붙인다.

        Cut을 하나씩 만들면 첫 위반에서 멈추고, 오류 위치(loc)도 컷 기준이라
        몇 번째 컷인지가 빠진다. 그러면 재요청 피드백이 "나레이션이 31자" 한 줄뿐이라
        LLM이 어디를 고칠지 몰라 같은 위반을 반복한다(GPT에서 실제로 관측됨).
        """
        out: list[str] = []
        for pos, c in enumerate(self.cuts, start=1):
            try:
                self._build_cut(c, pos)
            except ValidationError as exc:
                for e in exc.errors():
                    field = ".".join(str(p) for p in e["loc"])
                    where = f"cut{pos}.{field}" if field else f"cut{pos}"
                    out.append(f"{where}: {e['msg']}")
        return out

    def length_errors(self, settings: Settings) -> list[str]:
        """컷 수와 전체 길이가 허용 범위 안인지. 길이는 일기마다 LLM이 정한다."""
        out: list[str] = []
        n, total = len(self.cuts), sum(c.duration_seconds for c in self.cuts)
        if not settings.min_cuts <= n <= settings.max_cuts:
            out.append(
                f"컷이 {n}개다. {settings.min_cuts}~{settings.max_cuts}개여야 한다."
            )
        if not settings.min_total_seconds <= total <= settings.max_total_seconds:
            out.append(
                f"전체 길이가 {total}초다. {settings.min_total_seconds}~"
                f"{settings.max_total_seconds}초여야 한다. 컷 수나 컷 길이를 조정한다."
            )
        elif total >= settings.max_total_seconds - NEAR_CAP_SECONDS:
            # 상한은 목표가 아니다. 상한 근처인데 4초로 충분한 컷이 길게 잡혀 있으면 줄이게 한다.
            short = narration_max_chars(4)
            padded = [
                pos
                for pos, c in enumerate(self.cuts, start=1)
                if c.duration_seconds > 4 and c.narration and len(c.narration) <= short
            ]
            if padded:
                out.append(
                    f"전체 길이가 {total}초로 상한에 가깝다. 컷 "
                    + "·".join(map(str, padded))
                    + f"은 나레이션이 4초 상한({short}자) 안이니 동작이 하나면 4초로 줄인다."
                )
        return out

    @staticmethod
    def _build_cut(c: _CutDraft, index: int) -> Cut:
        # 컷 번호는 LLM이 쓴 값 대신 순서로 매긴다. 0부터 세는 모델이 있다.
        return Cut(
            index=index,
            image_prompt=c.image_prompt,
            motion_prompt=c.motion_prompt,
            narration=c.narration.strip() or None,
            dialogue=[Line(**line.model_dump()) for line in c.dialogue],
            camera_distance=c.camera_distance,
            duration_seconds=c.duration_seconds,
            mood=c.mood,
            location=c.location,
        )

    def to_storyboard(self) -> Storyboard:
        return Storyboard(
            protagonist=self.protagonist,
            supporting=self.supporting,
            distortions=self.distortions,
            locations=self.locations,
            cuts=[
                self._build_cut(c, pos)
                for pos, c in enumerate(self.cuts, start=1)
            ],
        )


def system_prompt(prompts: PromptLibrary, settings: Settings, protagonist_hint: str = "주인공") -> str:
    """스토리보드 LLM 시스템 프롬프트. 길이·글자 수 규칙의 숫자를 설정에서 채운다."""
    return prompts.render(
        "storyboard_planner.system.md",
        min_cuts=settings.min_cuts,
        max_cuts=settings.max_cuts,
        min_total_seconds=settings.min_total_seconds,
        max_total_seconds=settings.max_total_seconds,
        cut_durations=CUT_DURATIONS,
        narration_limits={d: narration_max_chars(d) for d in CUT_DURATIONS},
        dialogue_limits={
            d: dialogue_max_chars(d) for d in CUT_DURATIONS if d >= DIALOGUE_MIN_SECONDS
        },
        dialogue_min_seconds=DIALOGUE_MIN_SECONDS,
        silent_cut_seconds=SILENT_CUT_SECONDS,
        max_silent_run=MAX_SILENT_RUN,
        # 예시: 4초 나레이션 컷 뒤에 4초 무음 컷이 이어질 때 그 나레이션이 쓸 수 있는 글자 수.
        spanning_example_chars=narration_chars_for_window(8 - 2 * CROSSFADE_SECONDS),
        distancing_rules=prompts.distancing_rules,
        protagonist_hint=protagonist_hint,
        dialogue_max_lines=DIALOGUE_MAX_LINES,
        dialogue_min_lines=DIALOGUE_MIN_LINES,
    )


async def plan_storyboard(
    diary: DiaryInput,
    *,
    llm: LLMProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore | None = None,
) -> Storyboard:
    system = system_prompt(prompts, settings, diary.protagonist_name or "주인공")
    user = prompts.render(
        "storyboard_planner.user.j2",
        diary_text=diary.text,
        emotion_json=json.dumps(diary.emotion, ensure_ascii=False, indent=2),
        protagonist_name=diary.protagonist_name,
        handoff=storyboard_context(diary.handoff),
        min_total_seconds=settings.min_total_seconds,
        max_total_seconds=settings.max_total_seconds,
    )

    started = time.perf_counter()
    feedback = ""
    last_violations: list[str] = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft, meta = await llm.complete_json(
            system=system, user=user + feedback, schema=_StoryboardDraft
        )
        log.info(
            "스토리보드 시도 %d/%d — %.1fs, in=%d out=%d tokens",
            attempt, MAX_ATTEMPTS, meta.elapsed_s, meta.input_tokens, meta.output_tokens,
        )
        if job is not None:
            job.record_cost(f"storyboard attempt {attempt}", meta.cost_usd)

        if cut_errors := draft.length_errors(settings) + draft.cut_errors():
            # 컷 수·전체 길이 범위, 나레이션/대사 배타 규칙이나 글자 수 상한 위반.
            # 예외로 죽이지 않고 한 번에 모아 피드백으로 돌려준다(재요청은 3회뿐이다).
            last_violations = cut_errors
            log.warning("가드레일 위반 %d건, 재요청", len(last_violations))
            feedback = _feedback(last_violations, meta.raw_json)
            continue
        else:
            try:
                sb = draft.to_storyboard()
            except ValidationError as exc:
                # 컷별 규칙은 위에서 걸렀다. 여기는 대사 화자가 인물 목록에 없는 것
                # 같은 스토리보드 전체 규칙 위반이다.
                last_violations = [
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors()
                ]
                log.warning("가드레일 위반 %d건, 재요청", len(last_violations))
                feedback = _feedback(last_violations, meta.raw_json)
                continue
            violations = lint_storyboard(sb)
            if not violations:
                if job is not None:
                    job.save_storyboard(sb)
                    job.record_stage(
                        Stage.STORYBOARD,
                        elapsed_s=time.perf_counter() - started,
                        attempts=attempt,
                    )
                return sb
            last_violations = [str(v) for v in violations]

        log.warning("가드레일 위반 %d건, 재요청", len(last_violations))
        feedback = _feedback(last_violations, meta.raw_json)

    raise GuardrailViolation(
        f"{MAX_ATTEMPTS}회 시도했으나 연출 원칙을 만족하는 스토리보드를 얻지 못했다:\n"
        + "\n".join(f"  - {v}" for v in last_violations)
    )
