"""SFT 학습 데이터 정제 — 생성한 대화를 검사해서 학습용/검증용 파일로 나눈다.

왜 필요한가
    data/sft/generated*.jsonl은 GPT-4o가 쓴 대화라 상담 규칙을 어긴 응답이 섞여 있다
    (질문 두 개, 지어낸 기억 등). 그대로 학습하면 모델이 위반을 배운다.
    또 평가에 쓰는 문장이 학습 데이터에 들어 있으면 평가 점수가 부풀려진다.

하는 일 (대화 단위로 버린다 — 이유별 개수를 리포트에 남긴다)
    1. violation : 상담봇 응답 중 하나라도 응답 검증 규칙(check_reply)에 걸림
    2. crisis    : 사용자 발화 중 하나라도 위기(CRISIS)로 판정됨 — 앱이 따로 처리하는 영역
    3. eval_leak : 평가 시나리오(evaluate_counsel.SCENARIOS)나 위기 세트 문장과 같은 사용자 발화
    4. duplicate : 사용자 발화 순서가 이미 나온 대화와 똑같음
    5. too_short : 상담봇 응답이 2개 미만
    남은 대화의 system 메시지는 지금 서비스가 쓰는 build_system_prompt()로 바꾼다
    (학습 때와 서비스 때 프롬프트가 같아야 한다).

사용법
    python -X utf8 scripts/prepare_sft_data.py
    → data/sft/train.jsonl, data/sft/val.jsonl, data/sft/prepare-report.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.counsel_guardrail import RiskLevel, assess  # noqa: E402
from app.services.counsel_output_check import check_reply  # noqa: E402
from app.services.counsel_prompt import build_system_prompt  # noqa: E402

DEFAULT_INPUTS = [
    ROOT / "data" / "sft" / "generated.jsonl",
    ROOT / "data" / "sft" / "generated_v2.jsonl",
]


def _eval_texts() -> set[str]:
    """평가에 쓰는 사용자 문장 — 학습 데이터에 있으면 안 된다."""
    path = ROOT / "scripts" / "evaluate_counsel.py"
    spec = importlib.util.spec_from_file_location("evaluate_counsel", path)
    ev = importlib.util.module_from_spec(spec)
    sys.modules["evaluate_counsel"] = ev
    spec.loader.exec_module(ev)
    texts = {line for lines in ev.SCENARIOS.values() for line in lines}
    texts |= {case[0] for case in ev.TUNING_CASES + ev.HELDOUT_CASES}
    return {_norm(t) for t in texts}


def _norm(text: str) -> str:
    return "".join(text.split())


def check_conversation(messages: list[dict], eval_texts: set[str]) -> str | None:
    """버릴 이유. 통과하면 None."""
    users: list[str] = []
    replies = 0
    for m in messages:
        if m["role"] == "user":
            users.append(m["content"])
            if assess(m["content"]).level is RiskLevel.CRISIS:
                return "crisis"
            if _norm(m["content"]) in eval_texts:
                return "eval_leak"
        elif m["role"] == "assistant":
            replies += 1
            if check_reply(m["content"], user_texts=users):
                return "violation"
    if replies < 2:
        return "too_short"
    return None


def prepare(inputs: list[Path], val_ratio: float, seed: int) -> dict:
    system_prompt = build_system_prompt()
    eval_texts = _eval_texts()
    kept: list[dict] = []
    dropped: Counter[str] = Counter()
    seen: set[tuple[str, ...]] = set()
    total = 0

    for path in inputs:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            total += 1
            messages = [m for m in json.loads(line)["messages"] if m["role"] != "system"]
            reason = check_conversation(messages, eval_texts)
            key = tuple(_norm(m["content"]) for m in messages if m["role"] == "user")
            if reason is None and key in seen:
                reason = "duplicate"
            if reason:
                dropped[reason] += 1
                continue
            seen.add(key)
            kept.append({"messages": [{"role": "system", "content": system_prompt}, *messages]})

    random.Random(seed).shuffle(kept)
    n_val = max(1, round(len(kept) * val_ratio))
    return {
        "total": total,
        "dropped": dict(dropped),
        "val": kept[:n_val],
        "train": kept[n_val:],
        "chars": sum(len(m["content"]) for row in kept for m in row["messages"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SFT 학습 데이터 정제")
    parser.add_argument("--inputs", nargs="*", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "sft")
    args = parser.parse_args()

    result = prepare(args.inputs, args.val_ratio, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    for name in ("train", "val"):
        (args.out / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result[name]),
            encoding="utf-8",
        )

    report = [
        "# SFT 데이터 정제 결과",
        "",
        f"- 입력 대화: {result['total']}개 ({', '.join(p.name for p in args.inputs)})",
        f"- 버린 대화: {sum(result['dropped'].values())}개 {result['dropped'] or ''}",
        f"- 학습: {len(result['train'])}개 / 검증: {len(result['val'])}개 (seed {args.seed})",
        f"- 전체 글자 수: {result['chars']:,} (토큰 수·비용은 업로드 후 OpenAI 대시보드 기준)",
        "- system 메시지: 현재 build_system_prompt()로 통일",
        "",
        "버린 이유: violation=응답 규칙 위반, crisis=위기 발화 포함, "
        "eval_leak=평가 문장과 겹침, duplicate=중복, too_short=응답 2개 미만",
    ]
    (args.out / "prepare-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()