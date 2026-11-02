"""1''. 나레이션 다듬기 — 컷마다 따로 쓴 나레이션을 한 편의 이야기처럼 이어지게 고친다.

스토리보드는 컷 단위로 쓰여 "~했어요."가 끊겨 반복되기 쉽다. 컷 구성·대사·화면은 그대로 두고
나레이션 문장만 전체를 한 번에 보며 고친다. 덧붙이는 단계라 실패하면 원래 나레이션을 쓴다.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel

from ..config import narration_chars_for_window
from ..job import JobStore
from ..models import Cut, DiaryInput, Storyboard
from ..providers.base import LLMProvider

log = logging.getLogger(__name__)

RETRIES = 3
FLOW_ENDINGS = r"(는데|자|니|서),$"

SYSTEM = """너는 짧은 영상의 나레이션 대본을 다듬는 편집자다. 컷마다 따로 쓰인 나레이션을 소리 내어 읽었을 때
친구가 오늘 일을 이어서 들려주는 것처럼 고친다. 나레이션 문장만 고치고 대사와 컷 순서는 건드리지 않는다.

순서
1. read_aloud에 나레이션과 대사를 순서대로 놓고 한 편의 이야기로 먼저 말해 본다.
2. 그 이야기를 컷별 줄(lines)로 나눈다.

이어 말하기
- 장면이나 시간이 바뀌는 줄은 "오전엔", "점심엔", "퇴근하고", "집에 와서"처럼 때와 곳을 말하며 시작한다. 가장 자연스러운 연결이다.
- 쉼표 잇기는 두 줄을 붙여 읽어 한 문장으로 말이 될 때만 쓴다. "~했는데,"(뒤가 앞과 반대이거나 앞이 뒤의 배경일 때),
  "~하자,", "~하니,", "~더니,", "~해서,"(앞이 뒤의 이유일 때)만 쓴다. 나열하는 "~했고,"는 쓰지 않는다.
  예: "회의가 길어 늦게 나왔는데," → "지하철에서도 시계만 봤어요."
  나쁜 예: "조금 부담스러웠는데," → "도시락에 웃음이 났어요." (앞뒤가 상관없다)
- 앞줄이 뒷줄의 이유나 배경이면 문장을 끝내지 말고 잇는다. 한 편에 한두 곳은 그런 자리가 있다.
- "~어요."로 끝나는 줄이 네 줄 연달아 나오지 않게 쉼표 잇기나 "~더라고요"로 푼다.
- 같은 때와 곳 말("졸업식 뒤")을 한 편에서 두 번 쓰지 않는다. 마지막 줄 바로 앞줄은 쉼표로 잇지 않는다.
- 쉼표로 끝난 줄 뒤가 대사면 그 대사를 끌어내는 말("물어봤더니,")일 때만 쓴다. 잇기 어려우면 문장을 끝낸다. 억지로 잇는 것보다 낫다.
- 다음 목소리가 있는 컷으로만 이어지고, 쉼표로 끝나는 줄을 두 번 연달아 쓰지 않는다.
- "그 말에", "그래도", "결국", "그제야"처럼 관계를 보여주는 말은 꼭 필요한 곳에만, 한 편에 두 번 이하로 쓴다.
- 끝맺음은 "~했어요"가 기본이다. 직접 보고 느낀 일에만 가끔 "~더라고요"를 쓴다. "~네요", "~했죠", "~거든요"는 쓰지 않는다.
  같은 끝맺음이 이어져도 줄이 다 달라 어색하지 않으면 괜찮다. 끝맺음을 바꾸려고 말을 어색하게 만들지 않는다.

지킬 것
- 원래 줄의 사실과 감정을 빠뜨리지 않는다. 구체적인 표현("실컷 웃었어요", "시계만 보며")도 다른 말로 바꾸지 않고 앞뒤만 잇는다.
- 글자 수를 맞추려고 조사를 빼지 않는다. (X) "보고서 고쳤어요" → (O) "보고서를 고쳤어요". 넘치면 다른 말을 줄인다.
- 사실을 일기와 다른 순간으로 옮기지 않는다. 회의 중에 떨린 손을 회의가 끝난 뒤의 일로 쓰지 않는다.
- max_chars는 상한이지 채울 분량이 아니다. 칸을 채우려고 "떡볶이집에서 떡볶이를"처럼 말을 늘리거나 새 내용을 넣지 않는다.
- 마지막 줄은 일기 마지막 감정과 그 이유를 지금 대본 그대로 살린다.
- 한 줄에는 한 가지 일만 담는다. 일이 두 가지면 더 중요한 하나만 남긴다.
  (X) "집에선 단팥빵을 못 먹고 전화하니 엄마도 한참 말이 없었어요."
- "그 손길에", "발걸음이 무거웠어요"처럼 일기에 없는 꾸민 말 대신 일기에 적힌 동작을 그대로 쓴다.
  (X) "그 손길에 눈물이 났어요." → (O) "할머니가 손을 꼭 잡자 눈물이 났어요."
- 쉬운 입말로 쓴다. "기다리는 이"처럼 글에서 쓰는 말은 쓰지 않는다.
- 일기에 없는 사실, 감정, 이유를 만들지 않는다. "그래서"처럼 원인을 말하는 연결은 일기에 그 관계가 있을 때만 쓴다.
- 3인칭 해요체다. 1인칭, "~했다", "~함", 반말은 쓰지 않는다.
- 첫 줄은 지금처럼 "○○는/은"으로 시작한다. 마지막 줄은 일기 마지막 감정을 그대로 말하고 마침표로 끝낸다.
- 줄마다 max_chars를 넘지 않는다. 그 컷 화면(what_is_seen)과 어긋나는 내용을 넣지 않는다.
- 비유나 꾸민 말, "이후엔"처럼 글에서 쓰는 말을 쓰지 않는다. 사전에 있는 말만 쓴다."""


LISTENER_SYSTEM = """너는 짧은 영상의 나레이션 대본을 처음 듣는 사람이다. 대본을 소리 내어 읽어 보고, 한국어 화자가
듣자마자 이상하다고 느낄 줄만 짚는다.

짚을 것
- 말이 안 되거나 어색한 표현: "떡볶이에 실컷 웃었어요", "손이 잡혀 눈물이 났어요", "졸리게 도착했어요"
- 조사가 빠진 말, 누가 한 일인지 모르겠는 문장
- 쉼표로 끝난 줄을 다음 줄과 붙여 읽었을 때 한 문장이 되지 않거나, 앞뒤 관계(반대, 이유, 배경)가 분명하지 않은 곳
  (예: "책으로 진도를 따라갔는데," → "확인이 잦아 부담됐어요."는 왜 "~는데"인지 들리지 않는다)
- 한 줄에 두 가지 이상의 일을 담아 숨 가쁜 줄
- 일기에 없는 꾸민 말("그 손길에", "김치찌개 앞에서"처럼 일기의 장면을 바꿔 말한 것)
- 바로 앞줄과 뜻이 겹치는 줄
- 일기와 다른 사실, 일기에 없는 말, 빠진 마지막 감정
짚지 않을 것
- 주인공 이름: 일기 작성자에게 붙인 이름이라 일기에 없어도 된다. 3인칭으로 쓴 것도 맞다.
- 대사를 누가 말했는지: 화면에 그 사람이 보인다.
- 일기 내용 중 대본에 없는 것: 영상이 짧아 줄인 것이다. 마지막 감정만 확인한다.
문제없으면 issues를 비운다. 말투 취향이나 더 예쁘게 쓸 수 있다는 지적은 하지 않는다."""


class _Heard(BaseModel):
    issues: list[str]


class _Line(BaseModel):
    cut: int
    narration: str


class _Script(BaseModel):
    read_aloud: str = ""
    lines: list[_Line]


def continues_into_next(cut: Cut) -> bool:
    """나레이션이 쉼표로 끝나 다음 컷으로 말이 이어지는가."""
    return bool(cut.narration and cut.narration.rstrip().endswith(","))


def _limits(sb: Storyboard) -> dict[int, int]:
    return {i: narration_chars_for_window(w) for i, w in sb.narration_windows().items()}


def problems(sb: Storyboard, script: _Script) -> list[str]:
    """다듬은 대본이 지켜야 할 규칙 중 코드로 확인할 수 있는 것."""
    new = {line.cut: line.narration.strip() for line in script.lines}
    limits = _limits(sb)
    if set(new) != set(limits):
        return [f"나레이션 컷은 {sorted(limits)}이다. 이 컷을 모두, 이 컷만 쓴다."]
    if any(not text for text in new.values()):
        return ["빈 줄은 쓰지 않는다."]
    out = [f"컷 {i}: {len(text)}자로 상한 {limits[i]}자를 넘는다." for i, text in new.items() if len(text) > limits[i]]
    order = [c for c in sb.cuts if c.index in new]
    first = order[0]
    if new[first.index].split()[0] != first.narration.split()[0]:
        out.append(f"첫 줄은 \"{first.narration.split()[0]}\"로 시작한다.")
    for c in order:
        if new[c.index].endswith(",") and not re.search(FLOW_ENDINGS, new[c.index]):
            out.append(f"컷 {c.index}: 쉼표로 이을 때는 ~는데, ~자, ~니, ~더니, ~서로 끝낸다.")
        if re.search(r"(네요|죠|거든요)[.!?]?$", new[c.index]):
            out.append(f"컷 {c.index}: \"~네요\", \"~죠\", \"~거든요\"는 쓰지 않는다.")
        if re.search(r"(^|\s)(나|내|우리)[는를가의]?\s", new[c.index]):
            out.append(f"컷 {c.index}: 1인칭을 쓰지 않는다.")
    if new[order[-1].index].endswith(","):
        out.append("마지막 줄은 마침표로 끝낸다.")
    for pos, cut in enumerate(sb.cuts[:-1]):
        if new.get(cut.index, "").endswith(",") and sb.cuts[pos + 1].is_silent:
            out.append(f"컷 {cut.index}: 다음 컷이 무음이라 쉼표로 이어갈 수 없다.")
    for a, b in zip(order, order[1:]):
        if new[a.index].endswith(",") and new[b.index].endswith(","):
            out.append(f"컷 {a.index}, {b.index}: 쉼표로 끝나는 줄이 연달아 있다.")
    # 대사가 끼면 끝맺음이 끊겨 들리므로 나레이션이 바로 이어지는 구간만 센다.
    streak: list[int] = []
    for cut in sb.cuts:
        if cut.index in new and new[cut.index].rstrip(".").endswith("어요"):
            streak.append(cut.index)
            if len(streak) == 4:
                out.append(f"컷 {streak[0]}~{cut.index}: \"~어요.\"로 끝나는 줄이 네 줄 연달아 있다.")
        elif cut.is_silent is False:
            streak = []
    return out


def _brief(sb: Storyboard, diary: DiaryInput) -> str:
    limits = _limits(sb)
    cuts = []
    for c in sb.cuts:
        if c.dialogue:
            cuts.append({"cut": c.index, "dialogue": [line.text for line in c.dialogue]})
        elif c.narration:
            cuts.append({"cut": c.index, "narration": c.narration, "max_chars": limits[c.index],
                         "mood": c.mood, "what_is_seen": c.image_prompt})
        else:
            cuts.append({"cut": c.index, "silent": True})
    return f"## 일기\n\n{diary.text}\n\n## 지금 대본\n\n{json.dumps(cuts, ensure_ascii=False, indent=1)}"


def _closed(text: str) -> str:
    return text if text[-1] in ".,!?" else text + "."


def apply_script(sb: Storyboard, script: _Script) -> Storyboard:
    new = {line.cut: _closed(line.narration.strip()) for line in script.lines}
    cuts = [c.model_copy(update={"narration": new[c.index]}) if c.index in new else c for c in sb.cuts]
    return sb.model_copy(update={"cuts": cuts})


def _read_through(sb: Storyboard, diary: DiaryInput, script: _Script) -> str:
    lines = []
    for cut in apply_script(sb, script).cuts:
        if cut.dialogue:
            lines.append(f"컷 {cut.index} (대사): " + " ".join(line.text for line in cut.dialogue))
        elif cut.narration:
            lines.append(f"컷 {cut.index}: {cut.narration}")
    return f"## 일기\n\n{diary.text}\n\n## 대본\n\n" + "\n".join(lines)


async def polish_narration(
    sb: Storyboard, diary: DiaryInput, *, llm: LLMProvider, job: JobStore | None = None,
) -> Storyboard:
    if len(_limits(sb)) < 2:
        return sb
    user = _brief(sb, diary)
    passed: _Script | None = None
    fewest = 0
    for attempt in range(RETRIES + 1):
        try:
            script, meta = await llm.complete_json(system=SYSTEM, user=user, schema=_Script)
            if job:
                job.record_cost(f"narration polish {attempt + 1}", meta.cost_usd)
            issues = problems(sb, script)
            if not issues:
                heard, meta = await llm.complete_json(
                    system=LISTENER_SYSTEM, user=_read_through(sb, diary, script), schema=_Heard)
                if job:
                    job.record_cost(f"narration listen {attempt + 1}", meta.cost_usd)
                issues = heard.issues
                if passed is None or len(issues) < fewest:
                    passed, fewest = script, len(issues)
        except Exception as exc:  # 덧붙이는 단계다. 실패해도 스토리보드는 그대로 쓴다.
            log.warning("나레이션 다듬기 실패: %s", exc)
            break
        if not issues:
            break
        log.info("나레이션 다듬기 %d회차 지적: %s", attempt + 1, issues)
        user = _brief(sb, diary) + "\n\n## 직전 결과\n\n" + script.model_dump_json() + \
            "\n\n## 직전 결과의 문제\n\n" + "\n".join(f"- {i}" for i in issues) + \
            "\n\n지적받은 줄만 고치고 나머지 줄은 직전 결과 그대로 둔다. 고칠 때도 모든 규칙을 지킨다."
    if passed is None:
        log.warning("나레이션 다듬기가 규칙을 지키지 못해 원래 나레이션을 쓴다.")
        return sb
    out = apply_script(sb, passed)
    if job:
        job.save_storyboard(out)
    log.info("나레이션 다듬기: %s", [c.narration for c in out.cuts if c.narration])
    return out
