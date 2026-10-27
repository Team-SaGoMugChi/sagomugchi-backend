"""상담 평가 스크립트 — 과금 없는 위기 감지 평가가 돌고, 규칙이 개발 세트를 지키는지."""

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_counsel.py"
_spec = importlib.util.spec_from_file_location("evaluate_counsel", _PATH)
ev = importlib.util.module_from_spec(_spec)
sys.modules["evaluate_counsel"] = ev  # dataclass가 모듈을 찾을 수 있게 먼저 등록
_spec.loader.exec_module(ev)


def test_tuning_set_stays_fully_correct():
    # 개발 세트가 깨지면 규칙을 고치다가 기존 동작을 망가뜨린 것이다.
    result = ev.evaluate_crisis(ev.TUNING_CASES)
    assert result["three_level_accuracy"] == 1.0, result["mistakes"]


def test_v2_has_fewer_false_alarms_than_v1():
    result = ev.evaluate_crisis(ev.TUNING_CASES)
    assert result["binary_v2"]["false_alarm"] < result["binary_v1"]["false_alarm"]


def test_heldout_report_has_expected_shape():
    result = ev.evaluate_crisis(ev.HELDOUT_CASES)
    assert result["cases"] == len(ev.HELDOUT_CASES)
    assert {"missed_crisis", "false_alarm", "recall", "precision"} <= set(result["binary_v2"])


def test_markdown_puts_heldout_first():
    md = ev.render_markdown(
        ev.evaluate_crisis(ev.TUNING_CASES), ev.evaluate_crisis(ev.HELDOUT_CASES), None
    )
    assert md.index("### 검증 세트") < md.index("### 개발 세트")
    

def test_aggregate_live_reports_mean_and_std():
    base = {
        "model": "m", "turns": 2, "samples": [],
        "before_by_rule": {"multi_question": 1}, "after_by_rule": {},
        "violation_rate_after": 0.0, "regenerated_rate": 0.5,
        "repaired_rate": 0.0, "fallback_rate": 0.0, "exposed_rate": 0.0,
    }
    runs = [{**base, "violation_rate_before": v} for v in (0.2, 0.4)]
    agg = ev.aggregate_live(runs)
    assert agg["runs"] == 2
    assert agg["violation_rate_before"]["mean"] == 0.3
    assert agg["violation_rate_before"]["std"] > 0
    assert agg["before_by_rule"] == {"multi_question": 2}


def test_markdown_shows_judge_rows():
    tuning = ev.evaluate_crisis(ev.TUNING_CASES)
    heldout = ev.evaluate_crisis(ev.HELDOUT_CASES)
    judge = {
        "heldout_judge": heldout, "heldout_hybrid": heldout,
        "tuning_judge": tuning, "tuning_hybrid": tuning,
        "stats": {"model": "gpt-4o-mini", "calls": 1, "failed": 0, "avg_seconds": 0.5},
    }
    md = ev.render_markdown(tuning, heldout, None, judge)
    assert "v4 혼합(규칙+LLM)" in md
    assert md.index("### 검증 세트") < md.index("### 개발 세트")