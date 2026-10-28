"""상담 평가 수치 검증 — 신뢰구간, 유의성 검정, 사람 검수 일치도.

evaluate_counsel.py가 낸 숫자를 논문에 쓰기 전에 세 가지를 확인한다.
  1. 숫자가 얼마나 흔들리는가     → 신뢰구간 (ci)
  2. 두 방식의 차이가 우연인가    → McNemar(같은 문장 비교), 시나리오 부트스트랩(모델 비교)
  3. 자동 측정이 사람 판단과 맞는가 → 사람 검수 CSV를 받아 일치도(카파) 계산

사용법
    # 1) 신뢰구간
    python -X utf8 scripts/counsel_stats.py ci docs/evaluations/counsel-eval-2026-10-26-base.json
    # 2) 규칙 vs 혼합 판정 (같은 검증 문장) — McNemar
    python -X utf8 scripts/counsel_stats.py mcnemar docs/evaluations/counsel-eval-2026-10-26-base.json
    # 2) 기본 모델 vs SFT 모델 응답 위반율 차이
    python -X utf8 scripts/counsel_stats.py compare <base.json> <sft.json>
    # 3) 사람 검수 — 응답 (모델 이름을 가린 CSV를 만들고, 2명이 따로 채운 뒤 일치도 계산)
    python -X utf8 scripts/counsel_stats.py export-replies <base.json> <sft.json> --n 40
    python -X utf8 scripts/counsel_stats.py agree-replies review-A.csv review-B.csv
    # 3) 사람 검수 — 위기 라벨 (정답을 가린 CSV, 팀원 2~3명)
    python -X utf8 scripts/counsel_stats.py export-crisis
    python -X utf8 scripts/counsel_stats.py agree-crisis crisis-A.csv crisis-B.csv crisis-C.csv

검수 파일은 docs/evaluations/review/ 아래에 만든다. 정답 키(*-key.json)는 검수자에게 주지 않는다.
외부 라이브러리 없이 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "docs" / "evaluations" / "review"
RULES = (
    "diagnosis", "medication", "method", "fake_memory",
    "multi_question", "too_long", "false_comfort", "emoji",
)
SCORES = ("empathy", "helpfulness")  # 1~5점
LEVELS = ("crisis", "caution", "none")
BOOT = 2000


# ── 통계 도구 ─────────────────────────────────────────────────────────

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """비율의 95% 신뢰구간(Wilson). 표본이 작아도 0~1을 벗어나지 않는다."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def mcnemar_exact(b: int, c: int) -> float:
    """짝지은 두 방식의 정답/오답이 엇갈린 수 b, c로 구하는 양측 정확 p값."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    idx = (len(values) - 1) * q
    lo, hi = math.floor(idx), math.ceil(idx)
    return values[lo] + (values[hi] - values[lo]) * (idx - lo)


def cohen_kappa(a: list, b: list) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def weighted_kappa(a: list[int], b: list[int], lo: int = 1, hi: int = 5) -> float:
    """1~5점 척도용 2차 가중 카파."""
    n = len(a)
    if n == 0:
        return float("nan")
    k = hi - lo + 1
    w = lambda i, j: ((i - j) ** 2) / ((k - 1) ** 2)  # noqa: E731
    ca, cb = Counter(a), Counter(b)
    obs = sum(w(x, y) for x, y in zip(a, b)) / n
    exp = sum(w(i, j) * ca[i] * cb[j] for i in range(lo, hi + 1) for j in range(lo, hi + 1)) / (n * n)
    return 1.0 if exp == 0 else 1 - obs / exp


def fleiss_kappa(table: list[list[str]], categories: tuple[str, ...]) -> float:
    """[table] 문장마다 평가자들의 라벨 목록 (평가자 수는 같아야 한다)."""
    n_items, n_raters = len(table), len(table[0])
    counts = [[row.count(c) for c in categories] for row in table]
    p_j = [sum(r[j] for r in counts) / (n_items * n_raters) for j in range(len(categories))]
    p_i = [(sum(x * x for x in r) - n_raters) / (n_raters * (n_raters - 1)) for r in counts]
    p_bar, p_e = sum(p_i) / n_items, sum(p * p for p in p_j)
    return 1.0 if p_e == 1 else (p_bar - p_e) / (1 - p_e)


def _fmt(p: float) -> str:
    return f"{p * 100:.1f}%"


def _ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{_fmt(k / n if n else 0)} [{_fmt(lo)}, {_fmt(hi)}] ({k}/{n})"


# ── 1. 신뢰구간 ──────────────────────────────────────────────────────

def _crisis_counts(result: dict) -> dict:
    rows = result["rows"]
    tp = sum(r["expected"] == "crisis" and r["got"] == "crisis" for r in rows)
    pos = sum(r["expected"] == "crisis" for r in rows)
    pred = sum(r["got"] == "crisis" for r in rows)
    neg = len(rows) - pos
    fp = pred - tp
    return {"ok": sum(r["ok"] for r in rows), "n": len(rows), "tp": tp, "pos": pos,
            "pred": pred, "fp": fp, "neg": neg}


def _by_scenario(turn_log: list[dict], key: str) -> dict[str, list[int]]:
    """시나리오별 [위반 턴 수, 전체 턴 수] — 같은 대화의 턴은 서로 독립이 아니라 묶어서 뽑는다."""
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for t in turn_log:
        out[t["scenario"]][0] += bool(t[key])
        out[t["scenario"]][1] += 1
    return out


def _cluster_boot(groups: dict[str, list[int]], seed: int = 0) -> tuple[float, float]:
    names = list(groups)
    rng = random.Random(seed)
    rates = []
    for _ in range(BOOT):
        pick = [groups[rng.choice(names)] for _ in names]
        n = sum(p[1] for p in pick)
        rates.append(sum(p[0] for p in pick) / n if n else 0.0)
    return percentile(rates, 0.025), percentile(rates, 0.975)


def cmd_ci(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"# 95% 신뢰구간 — {path.name}\n")
    sets = [("규칙", data["crisis_heldout"])]
    if data.get("judge"):
        sets += [("LLM 단독", data["judge"]["heldout_judge"]), ("혼합", data["judge"]["heldout_hybrid"])]
    print("## 위기 판정 (검증 세트, Wilson)")
    for name, result in sets:
        c = _crisis_counts(result)
        print(f"- {name}: 정확도 {_ci(c['ok'], c['n'])} / CRISIS 재현율 {_ci(c['tp'], c['pos'])}"
              f" / 오탐률 {_ci(c['fp'], c['neg'])}")

    live = data.get("live")
    if live and live.get("turn_log"):
        log = live["turn_log"]
        print(f"\n## 응답 검증 ({live['model']}, {len(log)}턴 = {live['turns']}턴 × {live['runs']}회,"
              " 시나리오 단위 부트스트랩)")
        for key, label in (("first_violations", "검증 전 위반율"), ("exposed_violations", "사용자 노출 위반율")):
            groups = _by_scenario(log, key)
            k = sum(g[0] for g in groups.values())
            lo, hi = _cluster_boot(groups)
            print(f"- {label}: {_fmt(k / len(log))} [{_fmt(lo)}, {_fmt(hi)}] ({k}/{len(log)})")


# ── 2. 유의성 ────────────────────────────────────────────────────────

def cmd_mcnemar(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("judge"):
        raise SystemExit("--judge로 만든 결과 파일이 필요합니다.")
    rule = {r["text"]: r for r in data["crisis_heldout"]["rows"]}
    print(f"# 규칙 vs 혼합 — 같은 검증 문장 {len(rule)}개 (McNemar 정확 검정)\n")
    for name, other in (("LLM 단독", data["judge"]["heldout_judge"]), ("혼합", data["judge"]["heldout_hybrid"])):
        rows = {r["text"]: r for r in other["rows"]}
        for label, ok in (
            ("단계+축 정답", lambda r: r["ok"]),
            ("CRISIS 여부 정답", lambda r: (r["expected"] == "crisis") == (r["got"] == "crisis")),
        ):
            b = sum(ok(rule[t]) and not ok(rows[t]) for t in rule)  # 규칙만 맞음
            c = sum(not ok(rule[t]) and ok(rows[t]) for t in rule)  # 비교 방식만 맞음
            print(f"- 규칙 vs {name} [{label}]: 규칙만 맞음 {b} / {name}만 맞음 {c} → p = {mcnemar_exact(b, c):.4f}")
    print("\np < 0.05면 우연이라 보기 어려운 차이. 엇갈린 문장 수가 6개 미만이면 검정력이 거의 없다.")


def cmd_compare(path_a: Path, path_b: Path) -> None:
    a = json.loads(path_a.read_text(encoding="utf-8"))["live"]
    b = json.loads(path_b.read_text(encoding="utf-8"))["live"]
    print(f"# 응답 위반율 비교: {a['model']} vs {b['model']} (시나리오 짝지은 부트스트랩)\n")
    for key, label in (("first_violations", "검증 전 위반율"), ("exposed_violations", "사용자 노출 위반율")):
        ga, gb = _by_scenario(a["turn_log"], key), _by_scenario(b["turn_log"], key)
        names = sorted(set(ga) & set(gb))
        rate = lambda g, ns: sum(g[n][0] for n in ns) / sum(g[n][1] for n in ns)  # noqa: E731
        diff = rate(gb, names) - rate(ga, names)
        rng = random.Random(0)
        boots = []
        for _ in range(BOOT):
            pick = [rng.choice(names) for _ in names]
            boots.append(rate(gb, pick) - rate(ga, pick))
        lo, hi = percentile(boots, 0.025), percentile(boots, 0.975)
        p = min(1.0, 2 * min(sum(x <= 0 for x in boots), sum(x >= 0 for x in boots)) / BOOT)
        print(f"- {label}: {_fmt(rate(ga, names))} → {_fmt(rate(gb, names))}, "
              f"차이 {diff * 100:+.1f}%p [{lo * 100:+.1f}, {hi * 100:+.1f}], p ≈ {p:.3f}")
    print("\n신뢰구간이 0을 포함하면 두 모델 차이를 단정할 수 없다.")


# ── 3. 사람 검수 ─────────────────────────────────────────────────────

def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # 엑셀에서 한글이 안 깨지게
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cmd_export_replies(paths: list[Path], n: int, seed: int) -> None:
    rng = random.Random(seed)
    items, key = [], {}
    for path in paths:
        live = json.loads(path.read_text(encoding="utf-8"))["live"]
        log = list(live["turn_log"])
        rng.shuffle(log)
        for t in log[:n]:
            items.append((path.stem, live["model"], t))
    rng.shuffle(items)
    rows = []
    for i, (source, model, t) in enumerate(items, 1):
        rid = f"R{i:03d}"
        key[rid] = {"source": source, "model": model, "auto": t["first_violations"]}
        rows.append([rid, t["user"], t["raw"], *[""] * (len(RULES) + len(SCORES)), ""])
    header = ["id", "user", "reply", *RULES, *SCORES, "memo"]
    _write_csv(REVIEW_DIR / "replies-blank.csv", header, rows)
    (REVIEW_DIR / "replies-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"검수 파일: {REVIEW_DIR / 'replies-blank.csv'} ({len(rows)}개, 모델 이름 가림)")
    print("검수자마다 복사해서 채운다: 규칙 칸은 위반이면 1, 아니면 0 / empathy·helpfulness는 1~5점")
    print(f"정답 키 {REVIEW_DIR / 'replies-key.json'}는 검수자에게 주지 않는다.")


def cmd_agree_replies(path_a: Path, path_b: Path) -> None:
    key = json.loads((REVIEW_DIR / "replies-key.json").read_text(encoding="utf-8"))
    a = {r["id"]: r for r in _read_csv(path_a)}
    b = {r["id"]: r for r in _read_csv(path_b)}
    ids = sorted(set(a) & set(b) & set(key))
    flag = lambda r, rule: r[rule].strip() == "1"  # noqa: E731
    any_flag = lambda r: any(flag(r, rule) for rule in RULES)  # noqa: E731

    print(f"# 응답 검수 일치도 — {len(ids)}개\n")
    print("## 1) 검수자 두 명끼리 (Cohen's kappa)")
    print(f"- 위반 있음/없음: κ = {cohen_kappa([any_flag(a[i]) for i in ids], [any_flag(b[i]) for i in ids]):.2f}")
    for rule in RULES:
        xa, xb = [flag(a[i], rule) for i in ids], [flag(b[i], rule) for i in ids]
        if any(xa) or any(xb):
            print(f"- {rule}: κ = {cohen_kappa(xa, xb):.2f} (A {sum(xa)}개, B {sum(xb)}개)")

    agreed = [i for i in ids if any_flag(a[i]) == any_flag(b[i])]
    human = [any_flag(a[i]) for i in agreed]
    auto = [bool(key[i]["auto"]) for i in agreed]
    tp = sum(h and m for h, m in zip(human, auto))
    print(f"\n## 2) 자동 검사(check_reply) vs 사람 — 두 검수자가 일치한 {len(agreed)}개 기준")
    print(f"- 정밀도(자동이 위반이라 한 것 중 사람도 위반): {_ci(tp, sum(auto))}")
    print(f"- 재현율(사람이 위반이라 한 것 중 자동도 잡음): {_ci(tp, sum(human))}")
    print(f"- 일치도 κ = {cohen_kappa(human, auto):.2f}")

    print("\n## 3) 응답 품질 (1~5점, 두 검수자 평균)")
    for score in SCORES:
        pairs = [(int(a[i][score]), int(b[i][score])) for i in ids if a[i][score].strip() and b[i][score].strip()]
        if not pairs:
            continue
        print(f"- {score}: 검수자 일치 가중 κ = {weighted_kappa([p[0] for p in pairs], [p[1] for p in pairs]):.2f}")
        by_model: dict[str, list[float]] = defaultdict(list)
        for i in ids:
            if a[i][score].strip() and b[i][score].strip():
                by_model[key[i]["source"]].append((int(a[i][score]) + int(b[i][score])) / 2)
        rng = random.Random(0)
        for source, vals in sorted(by_model.items()):
            boots = [sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(BOOT)]
            print(f"  - {source}: 평균 {sum(vals) / len(vals):.2f} "
                  f"[{percentile(boots, 0.025):.2f}, {percentile(boots, 0.975):.2f}] (n={len(vals)})")
    print("\nκ 해석(Landis & Koch): 0.41~0.60 보통, 0.61~0.80 상당, 0.81 이상 거의 완전")


def _load_eval_module():
    spec = importlib.util.spec_from_file_location("evaluate_counsel", ROOT / "scripts" / "evaluate_counsel.py")
    ev = importlib.util.module_from_spec(spec)
    sys.modules["evaluate_counsel"] = ev
    spec.loader.exec_module(ev)
    return ev


def cmd_export_crisis(seed: int) -> None:
    ev = _load_eval_module()
    cases = list(ev.HELDOUT_CASES)
    random.Random(seed).shuffle(cases)
    key, rows = {}, []
    for i, case in enumerate(cases, 1):
        cid = f"C{i:03d}"
        key[cid] = {"text": case[0], "level": case[1], "axis": ev._expected_axis(case)}
        rows.append([cid, case[0], "", ""])
    _write_csv(REVIEW_DIR / "crisis-blank.csv", ["id", "text", "level", "axis"], rows)
    (REVIEW_DIR / "crisis-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"검수 파일: {REVIEW_DIR / 'crisis-blank.csv'} ({len(rows)}문장, 정답 가림)")
    print("level: crisis / caution / none, axis: suicide / danger / harm_others / psychosis / dependence (none이면 비움)")
    print("판단 기준으로 docs/CRISIS_POLICY.md의 '단계'와 '위험 축' 표만 보여 준다(규칙 코드는 보여 주지 않는다).")


def cmd_agree_crisis(paths: list[Path]) -> None:
    key = json.loads((REVIEW_DIR / "crisis-key.json").read_text(encoding="utf-8"))
    raters = [{r["id"]: r["level"].strip().lower() for r in _read_csv(p)} for p in paths]
    ids = sorted(set(key).intersection(*raters))
    print(f"# 위기 라벨 일치도 — 문장 {len(ids)}개, 검수자 {len(raters)}명\n")
    if len(raters) >= 2:
        table = [[r[i] for r in raters] for i in ids]
        print(f"- 검수자 간 일치 (Fleiss κ, 3단계): {fleiss_kappa(table, LEVELS):.2f}")
    gold = [key[i]["level"] for i in ids]
    for path, r in zip(paths, raters):
        labels = [r[i] for i in ids]
        ok = sum(x == y for x, y in zip(labels, gold))
        print(f"- {path.stem} vs 정답: 일치 {_ci(ok, len(ids))}, κ = {cohen_kappa(labels, gold):.2f}")
    majority = [Counter(r[i] for r in raters).most_common(1)[0][0] for i in ids]
    disagree = [i for i, m in zip(ids, majority) if m != key[i]["level"]]
    print(f"- 다수결 vs 정답 불일치 {len(disagree)}문장:")
    for i in disagree:
        print(f"  - {key[i]['text']} — 정답 {key[i]['level']}, 다수결 {majority[ids.index(i)]}")
    print("\n불일치 문장은 팀이 다시 논의해 정답을 확정하고, 바꾼 경우 그 사실을 논문에 적는다.")


def main() -> None:
    parser = argparse.ArgumentParser(description="상담 평가 수치 검증")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ci").add_argument("file", type=Path)
    sub.add_parser("mcnemar").add_argument("file", type=Path)
    p = sub.add_parser("compare")
    p.add_argument("base", type=Path)
    p.add_argument("other", type=Path)
    p = sub.add_parser("export-replies")
    p.add_argument("files", type=Path, nargs="+")
    p.add_argument("--n", type=int, default=40, help="파일마다 뽑을 턴 수")
    p.add_argument("--seed", type=int, default=42)
    p = sub.add_parser("agree-replies")
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p = sub.add_parser("export-crisis")
    p.add_argument("--seed", type=int, default=42)
    sub.add_parser("agree-crisis").add_argument("files", type=Path, nargs="+")
    args = parser.parse_args()

    if args.cmd == "ci":
        cmd_ci(args.file)
    elif args.cmd == "mcnemar":
        cmd_mcnemar(args.file)
    elif args.cmd == "compare":
        cmd_compare(args.base, args.other)
    elif args.cmd == "export-replies":
        cmd_export_replies(args.files, args.n, args.seed)
    elif args.cmd == "agree-replies":
        cmd_agree_replies(args.a, args.b)
    elif args.cmd == "export-crisis":
        cmd_export_crisis(args.seed)
    else:
        cmd_agree_crisis(args.files)


if __name__ == "__main__":
    main()