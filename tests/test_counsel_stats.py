"""평가 통계 도구 — 알려진 값으로 계산이 맞는지 확인한다."""

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "counsel_stats.py"
_spec = importlib.util.spec_from_file_location("counsel_stats", _PATH)
st = importlib.util.module_from_spec(_spec)
sys.modules["counsel_stats"] = st
_spec.loader.exec_module(st)


def test_wilson_stays_in_range():
    lo, hi = st.wilson(0, 3)
    assert lo == 0.0 and 0.5 < hi < 0.6  # 0/3이어도 상한은 56% 정도


def test_mcnemar_exact_known_values():
    assert st.mcnemar_exact(0, 3) == 0.25
    assert round(st.mcnemar_exact(1, 9), 4) == 0.0215
    assert st.mcnemar_exact(0, 0) == 1.0


def test_cohen_kappa_perfect_and_chance():
    assert st.cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert st.cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == 0.0


def test_weighted_kappa_penalises_far_disagreement():
    near = st.weighted_kappa([1, 2, 3, 4, 5], [2, 2, 3, 4, 5])
    far = st.weighted_kappa([1, 2, 3, 4, 5], [5, 2, 3, 4, 1])
    assert near > far


def test_fleiss_kappa_perfect_agreement():
    table = [["crisis"] * 3, ["none"] * 3, ["caution"] * 3]
    assert st.fleiss_kappa(table, st.LEVELS) == 1.0