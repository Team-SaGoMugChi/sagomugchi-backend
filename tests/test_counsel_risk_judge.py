"""위기 판정 2단계 — LLM은 단계를 올리기만 하고, 실패하면 규칙 결과를 쓴다."""

import json

from app.services import counsel_risk_judge as judge
from app.services.counsel_guardrail import RiskAssessment, RiskAxis, RiskLevel


def _fake(level: str, axis: str | None = "suicide", calls: list | None = None):
    def chat(system_prompt, messages, **kwargs):
        if calls is not None:
            calls.append(messages[-1]["content"])
        return json.dumps({"level": level, "axis": axis})

    return chat


def _boom(*args, **kwargs):
    raise TimeoutError


def test_llm_escalates_missed_paraphrase():
    result = judge.assess_hybrid("더 살아서 뭐해", chat=_fake("crisis"))
    assert result.level is RiskLevel.CRISIS
    assert result.axis is RiskAxis.SUICIDE
    assert result.reason == "llm_judge"


def test_llm_never_lowers_rule_result():
    # 규칙이 CAUTION인 문장을 LLM이 none이라 해도 CAUTION 유지
    result = judge.assess_hybrid("친구가 자해한다고 해서 걱정돼", chat=_fake("none", None))
    assert result.level is RiskLevel.CAUTION


def test_rule_crisis_skips_llm():
    calls: list = []
    result = judge.assess_hybrid("요즘 죽고 싶다는 생각이 자주 들어", chat=_fake("none", None, calls))
    assert result.level is RiskLevel.CRISIS
    assert calls == []


def test_llm_failure_falls_back_to_rule():
    result = judge.assess_hybrid("배고파 죽겠어", chat=_boom)
    assert result.level is RiskLevel.NONE


def test_invalid_json_falls_back_to_rule():
    result = judge.assess_hybrid("오늘 회의 길었어", chat=lambda *a, **k: "위기 아님")
    assert result.level is RiskLevel.NONE


def test_dependence_is_never_crisis():
    parsed = judge.parse_judgement('{"level": "crisis", "axis": "dependence"}')
    assert parsed.level is RiskLevel.CAUTION
    assert parsed.axis is RiskAxis.DEPENDENCE


def test_unknown_axis_defaults_to_suicide():
    parsed = judge.parse_judgement('{"level": "caution", "axis": "???"}')
    assert parsed.axis is RiskAxis.SUICIDE


def test_merge_keeps_rule_on_same_level():
    rule = RiskAssessment(RiskLevel.CAUTION, RiskAxis.DANGER)
    llm = RiskAssessment(RiskLevel.CAUTION, RiskAxis.SUICIDE)
    assert judge.merge(rule, llm) is rule