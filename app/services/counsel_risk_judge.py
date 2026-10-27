"""위기 판정 2단계 — 규칙(assess)이 CRISIS가 아니라고 본 발화를 LLM이 한 번 더 본다.

왜 필요한가
    규칙은 본 적 있는 표현에는 정확하지만 처음 보는 바꿔 말하기를 놓친다.
    2026-10-21 검증 세트에서 틀린 7문장이 모두 이런 미탐이었다
    (docs/evaluations/counsel-eval-2026-10-21.md).

합치는 규칙 (merge)
    - 규칙이 CRISIS면 LLM을 부르지 않는다. 지연·비용 없이 바로 안내한다.
    - LLM은 단계를 올리기만 한다. 규칙보다 낮게 보면 규칙 결과를 쓴다.
    - LLM 호출이 실패하거나 JSON이 깨지면 규칙 결과를 그대로 쓴다.
    - AI 의존은 정책상 CRISIS로 만들지 않는다(docs/CRISIS_POLICY.md).

주의
    JUDGE_PROMPT는 docs/CRISIS_POLICY.md와 개발 세트 문장만 보고 썼다.
    검증 세트 결과를 보고 프롬프트를 고치면 그 검증 세트는 더 이상 검증 세트가 아니다.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from app.core.config import get_settings
from app.services import llm_client
from app.services.counsel_guardrail import (
    RiskAssessment,
    RiskAxis,
    RiskLevel,
    assess,
)

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """너는 한국어 상담 앱의 위기 발화 분류기다.
사용자 발화 한 문장을 읽고 위험 단계와 축을 JSON으로만 답한다.

[단계]
- crisis : 지금 죽고 싶거나 스스로를 해치려는 마음, 그 방법·계획,
           지금 폭력을 당하는 중, 흉기를 들고 남을 해치려는 계획,
           해치라고 시키는 목소리(명령 환청)
- caution: 위험과 관련 있지만 지금 위기라고 단정할 수 없는 말
           (지난 경험, 남의 이야기, 뉴스·영화 이야기, 홧김에 하는 분노 표현,
            감시받거나 목소리가 들리는 경험, AI에게만 의지하려는 말)
- none   : 위 둘에 해당하지 않는 말

[축]
suicide(자살·자해), danger(폭력 피해), harm_others(남을 해침),
psychosis(현실 검증), dependence(AI 의존)

[기준]
- 죽음이라는 단어가 없어도 삶을 멈추고 싶다는 뜻이면 suicide다.
  예: "아침에 눈 안 떴으면 좋겠어" → crisis/suicide
- "~해 죽겠다", "죽을 것 같다", "죽는 줄 알았어"는 강조 표현이라 none이다.
  예: "배고파 죽겠어" → none
- 웃음(ㅋㅋ)이 붙어도 위험을 낮추지 않는다.
- 친구 등 남의 위기를 전하는 말은 caution이다.
  예: "친구가 자해한다고 해서 걱정돼" → caution/suicide
- AI 의존은 crisis가 아니다. 예: "나한테는 너밖에 없어" → caution/dependence
- crisis와 caution 사이에서 애매하면 caution, caution과 none 사이에서 애매하면 caution을 고른다.

[출력 — JSON 한 줄만]
{"level": "crisis" | "caution" | "none", "axis": "suicide" | "danger" | "harm_others" | "psychosis" | "dependence" | null}
"""

_LEVELS = {level.value: level for level in RiskLevel}
_AXES = {axis.value: axis for axis in RiskAxis}
_RANK = {RiskLevel.NONE: 0, RiskLevel.CAUTION: 1, RiskLevel.CRISIS: 2}

ChatFn = Callable[..., str]


def parse_judgement(raw: str) -> RiskAssessment | None:
    """LLM 출력(JSON) → RiskAssessment. 형식이 틀리면 None."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    level = _LEVELS.get(str(data.get("level", "")).strip().lower())
    if level is None:
        return None
    if level is RiskLevel.NONE:
        return RiskAssessment(RiskLevel.NONE, reason="llm_judge")

    axis = _AXES.get(str(data.get("axis") or "").strip().lower(), RiskAxis.SUICIDE)
    if axis is RiskAxis.DEPENDENCE and level is RiskLevel.CRISIS:
        level = RiskLevel.CAUTION  # 정책: 의존은 상담을 끊지 않는다
    return RiskAssessment(level, axis, reason="llm_judge")


def judge(text: str, *, chat: ChatFn | None = None) -> RiskAssessment | None:
    """LLM 판정 한 번. 실패하면 None (호출하는 쪽이 규칙 결과로 진행)."""
    settings = get_settings()
    chat = chat or llm_client.chat
    try:
        raw = chat(
            JUDGE_PROMPT,
            [{"role": "user", "content": text}],
            temperature=0,
            max_tokens=60,
            json_mode=True,
            model=settings.counsel_judge_model,
            timeout=settings.counsel_judge_timeout_sec,
        )
    except Exception as exc:  # 키 없음·타임아웃·네트워크 — 규칙 결과로 진행
        logger.warning("risk judge failed: %s", type(exc).__name__)
        return None

    result = parse_judgement(raw)
    if result is None:
        logger.warning("risk judge returned invalid output")
    return result


def merge(rule: RiskAssessment, llm: RiskAssessment | None) -> RiskAssessment:
    """LLM은 단계를 올리기만 한다."""
    if llm is None or _RANK[llm.level] <= _RANK[rule.level]:
        return rule
    return llm


def assess_hybrid(text: str, *, chat: ChatFn | None = None) -> RiskAssessment:
    """규칙 1차 + LLM 2차. 규칙이 CRISIS면 LLM을 부르지 않는다."""
    rule = assess(text)
    if rule.level is RiskLevel.CRISIS or not text.strip():
        return rule
    return merge(rule, judge(text, chat=chat))