"""CBT 단계형 SFT 데이터 정제 — 회기를 검사해서 턴 단위 학습용/검증용 파일로 만든다.

입력: data/sft/cbt_sessions.jsonl (generate_cbt_sft_data.py가 만든 회기)
출력: data/sft/cbt_train.jsonl, data/sft/cbt_val.jsonl, data/sft/cbt-prepare-report.md
      --review를 주면 사람이 읽고 검수할 data/sft/cbt-review.md도 만든다.

한 턴 = 학습 예시 하나 (서비스의 /counsel/turn 요청 하나와 같다)
    prompt     : [그 턴 단계의 시스템 프롬프트, 지난 턴(평문), 이번 사용자 발화]
    completion : [상담봇 JSON {"reply", "advance", "extracted"}]
    공개 모델 SFT(TRL SFTTrainer)의 대화형 prompt-completion 형식이라 completion만 학습한다.

버리는 기준
    - 회기 단위: 검수에서 뺀 회기(data/sft/cbt_drop.txt에 id 한 줄씩), 턴 2개 미만,
      평가 문장과 겹치는 사용자 발화(eval_leak)
    - 턴 단위: 생성 뒤 손으로 고친 응답이 규칙을 어기면 그 턴부터 회기 끝까지 버린다
      (뒤 턴의 history에 그 응답이 들어가므로)

검증용은 회기 단위로 나눈다. 같은 회기의 턴이 학습·검증에 섞이면 점수가 부풀려진다.

사용법
    python -X utf8 scripts/prepare_cbt_sft_data.py --review
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_cbt_sft_data import (  # noqa: E402
    history_for,
    problems,
    system_prompt_for,
)
from prepare_sft_data import _eval_texts, _norm  # noqa: E402

from app.services.counsel_cbt import STAGE_NAMES  # noqa: E402

SFT_DIR = ROOT / "data" / "sft"


def completion_json(turn: dict) -> str:
    """상담봇 정답 — 서비스가 기대하는 JSON 한 줄."""
    return json.dumps(
        {"reply": turn["reply"], "advance": turn["advance"], "extracted": turn["extracted"]},
        ensure_ascii=False,
    )


def session_examples(session: dict) -> tuple[list[dict], str | None]:
    """회기 하나 → 턴 단위 예시. 중간에 문제가 있으면 그 앞까지만 쓴다."""
    ctx = session["context"]
    turns = session["turns"]
    examples: list[dict] = []
    for i, turn in enumerate(turns):
        user_texts = [t["user"] for t in turns[: i + 1]]
        found = problems(completion_json(turn), turn["stage"], user_texts, ctx)
        if found:
            return examples, found[0]
        examples.append(
            {
                "session": session["id"],
                "stage": turn["stage"],
                "prompt": [
                    {"role": "system", "content": system_prompt_for(ctx, turn["stage"])},
                    *history_for(turns[:i]),
                    {"role": "user", "content": turn["user"]},
                ],
                "completion": [{"role": "assistant", "content": completion_json(turn)}],
            }
        )
    return examples, None


def review_markdown(sessions: list[dict]) -> str:
    """검수용 — 회기마다 단계·사용자·상담봇·추출값을 표로 보여준다."""
    lines = [
        "# CBT SFT 데이터 검수",
        "",
        "빼야 할 회기는 id를 data/sft/cbt_drop.txt에 한 줄씩 적고 다시 정제한다.",
        "기준: data/sft/README.md 검수 기준 + 단계에 맞는 질문인지, extracted가 사용자 말과 맞는지",
        "",
    ]
    for s in sessions:
        ctx = s["context"]
        lines += [
            f"## {s['id']} — {s['end_reason']}",
            f"- 일기: {ctx['diary_summary']} / 말투: {ctx['user_style']} / 스타일: {ctx['style']}",
            f"- 지난 미션: {ctx['last_mission'] or '없음'}"
            + (f" ({ctx['mission_result']})" if ctx["last_mission"] else ""),
            "",
            "| 단계 | 사용자 | 상담봇 | 다음 | extracted |",
            "|---|---|---|---|---|",
        ]
        for t in s["turns"]:
            cells = [
                f"{t['stage']} {STAGE_NAMES[t['stage']]}",
                t["user"],
                t["reply"],
                "→" if t["advance"] else "",
                json.dumps(t["extracted"], ensure_ascii=False),
            ]
            lines.append("| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="CBT 단계형 SFT 데이터 정제")
    parser.add_argument("--input", type=Path, default=SFT_DIR / "cbt_sessions.jsonl")
    parser.add_argument("--drop", type=Path, default=SFT_DIR / "cbt_drop.txt")
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=SFT_DIR)
    parser.add_argument("--review", action="store_true", help="검수용 cbt-review.md도 만든다")
    args = parser.parse_args()

    sessions = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    drop_ids = (
        {x.strip() for x in args.drop.read_text(encoding="utf-8").splitlines() if x.strip()}
        if args.drop.exists()
        else set()
    )
    eval_texts = _eval_texts()

    kept: list[tuple[str, list[dict]]] = []
    dropped: Counter[str] = Counter()
    cut: Counter[str] = Counter()
    for s in sessions:
        if s["id"] in drop_ids:
            dropped["review_drop"] += 1
            continue
        if any(_norm(t["user"]) in eval_texts for t in s["turns"]):
            dropped["eval_leak"] += 1
            continue
        examples, reason = session_examples(s)
        if reason:
            cut[reason] += 1
        if len(examples) < 2:
            dropped["too_short"] += 1
            continue
        kept.append((s["id"], examples))

    random.Random(args.seed).shuffle(kept)
    n_val = max(1, round(len(kept) * args.val_ratio)) if kept else 0
    split = {"val": kept[:n_val], "train": kept[n_val:]}

    args.out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    stage_count: Counter[int] = Counter()
    for name, group in split.items():
        rows = [ex for _, examples in group for ex in examples]
        counts[name] = len(rows)
        if name == "train":
            stage_count.update(ex["stage"] for ex in rows)
        (args.out / f"cbt_{name}.jsonl").write_text(
            "".join(
                json.dumps({"prompt": ex["prompt"], "completion": ex["completion"]}, ensure_ascii=False)
                + "\n"
                for ex in rows
            ),
            encoding="utf-8",
        )

    ends = Counter(s["end_reason"] for s in sessions)
    report = [
        "# CBT SFT 데이터 정제 결과",
        "",
        f"- 입력 회기: {len(sessions)}개 (끝난 이유 {dict(ends)})",
        f"- 버린 회기: {sum(dropped.values())}개 {dict(dropped) or ''}",
        f"- 중간에서 자른 회기: {sum(cut.values())}개 {dict(cut) or ''}",
        f"- 학습: {len(split['train'])}회기 / {counts.get('train', 0)}턴",
        f"- 검증: {len(split['val'])}회기 / {counts.get('val', 0)}턴 (회기 단위 분할, seed {args.seed})",
        "- 학습 턴의 단계 분포: "
        + ", ".join(f"{k} {STAGE_NAMES[k]} {stage_count[k]}" for k in sorted(stage_count)),
        "",
        "형식: TRL 대화형 prompt-completion (completion = 상담봇 JSON 한 줄)",
    ]
    (args.out / "cbt-prepare-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))

    if args.review:
        path = args.out / "cbt-review.md"
        path.write_text(review_markdown(sessions), encoding="utf-8")
        print(f"\n검수용 → {path}")


if __name__ == "__main__":
    main()