"""CBT 단계형 상담 — 상담 한 회기를 정해진 단계로 진행한다.

기존 `/counsel/turn`은 [상담 절차]를 프롬프트에 적어두고 LLM이 알아서 단계를
고르게 했다. 이 모듈은 요청에 `cbt`가 있을 때만 쓰이며, 서버가 지금 단계를
정해 주고 LLM은 그 단계 하나에만 집중한다. 단계 결과(자동적 사고, 대안 사고,
미션 등)는 JSON으로 받아 앱이 CounselSession에 저장한다.

단계와 근거
    0 지난 미션 확인  과제 수행률이 CBT 효과를 예측한다 — 회기 간 과제 연동
    1 감정 확인      감정 명명(affect labeling, Lieberman)
    2 자동적 사고    CBT 사고기록(Beck): 상황 → 자동적 사고
    3 거리두기       자기 거리두기(Kross·Ayduk) + 멀티모달 모순 제시 — Oddo 차별점
    4 대안 사고      인지 재구성: 근거·반대 근거 → 균형 잡힌 생각
    5 행동 가이드    행동활성화: 5분 안에 할 수 있는 작은 행동 하나

진행 규칙
    - 지난 미션이 없으면 0단계를 건너뛴다.
    - LLM이 advance=true를 주거나 한 단계에서 MAX_STAGE_TURNS 턴이 지나면 다음 단계로.
    - 5단계에서 넘어가면 회기 종료(done).

위기 발화는 이 모듈 전에 `counsel_guardrail.assess()`가 거른다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

FIRST_STAGE = 0
LAST_STAGE = 5
MAX_STAGE_TURNS = 3

STAGE_NAMES: dict[int, str] = {
    0: "지난 미션 확인",
    1: "감정 확인",
    2: "상황·자동적 사고",
    3: "거리두기",
    4: "대안 사고",
    5: "행동 가이드",
}

STYLE_PROMPTS: dict[str, str] = {
    "empathy": "[상담 스타일: 공감형]\n따뜻하고 부드럽게 말한다. 감정을 충분히 반영한 뒤에 질문한다.",
    "analysis": "[상담 스타일: 분석형]\n차분하고 구조적으로 말한다. 상황·생각·감정을 구분해서 짚어준다.",
    "goal": "[상담 스타일: 목표형]\n간결하고 실용적으로 말한다. 대화를 작은 행동 쪽으로 이끈다.",
}

_STAGE_PROMPTS: dict[int, str] = {
    0: """목표: 지난번에 정한 미션을 실제로 해봤는지 확인한다.
- 지난 미션: {last_mission}
- 했다면 구체적으로 인정하고, 해본 뒤 기분이 어땠는지 묻는다.
- 못 했다면 탓하지 않고, 무엇이 어려웠는지 한 번만 묻는다.
advance 조건: 수행 여부를 확인했으면 true
extracted 키: "missionDone"(true/false), "missionFeedback"(문자열)""",
    1: """목표: 사용자가 지금 감정에 직접 이름을 붙이게 한다.
- [오늘의 맥락]의 분석된 감정이 있으면 참고로만 보여주고 실제 느낌과 맞는지 묻는다.
- 감정 단어를 얻은 뒤 강도를 0~10으로 묻는다.
advance 조건: 감정 단어와 강도를 모두 얻었으면 true
extracted 키: "emotionLabel"(문자열), "intensity"(0~10 숫자)""",
    2: """목표: 감정을 일으킨 상황과 그 순간 스친 생각(자동적 사고)을 찾는다.
- [오늘 일기 사실]에 이미 있는 상황은 다시 묻지 않고 확인만 한다.
- "그 순간 머릿속에 어떤 생각이 스쳤어요?"처럼 생각을 묻는다.
- 감정만 말하면 생각으로 다시 이끈다.
advance 조건: 상황과 생각 문장을 모두 얻었으면 true
extracted 키: "situation"(문자열), "automaticThought"(문자열)""",
    3: """목표: 그 생각을 한 발 떨어져서 보게 한다.
- [말과 신호의 차이]가 있으면 그것을 부드럽게 한 번 짚는다.
- 없으면 "친한 친구가 같은 생각을 한다면 뭐라고 말해줄 것 같아요?"처럼 관점을 바꾸는 질문을 한다.
- 그 생각을 지금 얼마나 믿는지 0~100으로 묻는다.
advance 조건: 새로운 시각의 답과 믿음 정도를 얻었으면 true
extracted 키: "insight"(문자열), "beliefBefore"(0~100 숫자)""",
    4: """목표: 균형 잡힌 대안 생각을 사용자가 직접 만들게 한다.
- 그 생각을 뒷받침하는 근거와 그렇지 않은 근거를 하나씩 묻는다.
- 대안 생각을 대신 만들어주지 않고, 사용자의 말을 다듬어주기만 한다.
- 대안 생각을 얼마나 믿는지 0~100으로 묻는다.
advance 조건: 대안 생각과 믿음 정도를 얻었으면 true
extracted 키: "evidenceFor", "evidenceAgainst", "alternativeThought"(문자열), "beliefAfter"(0~100 숫자)""",
    5: """목표: 내일 해볼 작은 행동 하나를 함께 정하고 마무리한다.
- 5분 안에 할 수 있고 구체적인 행동이어야 한다. 예: 점심 먹고 10분 산책
- 선택지를 두 개 제안하되 사용자가 고르거나 고치게 한다.
- 정해지면 오늘 대화를 한 문장으로 정리하고 마무리한다.
advance 조건: 미션이 정해졌으면 true
extracted 키: "mission"(문자열), "sessionSummary"(문자열)""",
}

_OUTPUT_RULE = """[출력 형식]
반드시 아래 JSON 객체 하나만 출력한다. 다른 글은 쓰지 않는다.
{"reply": "사용자에게 할 말", "advance": true 또는 false, "extracted": {이번 단계에서 얻은 값}}
- reply는 위의 말투 규칙을 그대로 지킨다(2~3문장, 질문은 하나).
- extracted에는 사용자가 실제로 말한 값만 넣는다. 아직 모르는 키는 빼고, 지어내지 않는다.
- 사용자가 답하기 어려워하거나 거부하면 강요하지 말고 advance를 true로 한다."""


@dataclass
class CbtOutput:
    reply: str
    advance: bool = False
    extracted: dict[str, Any] = field(default_factory=dict)


def resolve_stage(stage: int, last_mission: str | None) -> int:
    """지난 미션이 없으면 0단계를 건너뛴다."""
    if stage == FIRST_STAGE and not (last_mission or "").strip():
        return FIRST_STAGE + 1
    return stage


def build_cbt_prompt(
    stage: int,
    style: str = "empathy",
    last_mission: str | None = None,
) -> str:
    """기존 시스템 프롬프트 뒤에 붙일 단계 지침."""
    body = _STAGE_PROMPTS[stage].format(last_mission=last_mission or "없음")
    return (
        "\n\n"
        + STYLE_PROMPTS.get(style, STYLE_PROMPTS["empathy"])
        + f"\n\n[현재 CBT 단계: {stage}. {STAGE_NAMES[stage]}]\n"
        "위 [상담 절차] 중 이번 턴에는 이 단계에만 집중한다. 다음 단계로 앞서가지 않는다.\n"
        + body
        + "\n\n"
        + _OUTPUT_RULE
    )


def parse_output(raw: str) -> CbtOutput:
    """LLM의 JSON 응답을 읽는다. JSON이 깨졌으면 원문을 reply로 쓰고 단계는 유지한다."""
    text = (raw or "").strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return CbtOutput(reply=text)
    if not isinstance(data, dict):
        return CbtOutput(reply=text)

    extracted = data.get("extracted")
    return CbtOutput(
        reply=str(data.get("reply") or "").strip(),
        advance=data.get("advance") is True,
        extracted=extracted if isinstance(extracted, dict) else {},
    )


def next_state(stage: int, stage_turn: int, advance: bool) -> tuple[int, int, bool]:
    """(다음 단계, 그 단계에서 지난 턴 수, 회기 종료 여부)."""
    turn = stage_turn + 1
    if not (advance or turn >= MAX_STAGE_TURNS):
        return stage, turn, False
    if stage >= LAST_STAGE:
        return LAST_STAGE, 0, True
    return stage + 1, 0, False