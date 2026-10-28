"""상담봇 SFT(파인튜닝) 실행 — OpenAI 파인튜닝 작업을 만들고 상태를 본다.

먼저 scripts/prepare_sft_data.py로 data/sft/train.jsonl, val.jsonl을 만든다.

사용법
    python -X utf8 scripts/finetune_counsel.py create                       # gpt-4o 기본
    python -X utf8 scripts/finetune_counsel.py create --base gpt-4o-mini-2024-07-18
    python -X utf8 scripts/finetune_counsel.py status ftjob-...              # 진행 상황·손실값

학습이 끝나면 status가 ft:...로 시작하는 모델 이름을 보여 준다.
비교 평가: evaluate_counsel.py --live --runs 3 --model <ft 모델> --tag sft
서비스에 쓰려면 .env의 LLM_MODEL을 그 이름으로 바꾼다(코드 수정 없음).

주의: 학습은 과금된다. 파인튜닝 가능한 모델과 가격은 OpenAI 문서에서 확인한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openai import OpenAI  # noqa: E402

from app.core.config import get_settings  # noqa: E402

SFT_DIR = ROOT / "data" / "sft"
JOB_LOG = SFT_DIR / "finetune-jobs.md"


def _client() -> OpenAI:
    key = get_settings().llm_api_key
    if not key:
        raise SystemExit("LLM_API_KEY가 .env에 없습니다.")
    return OpenAI(api_key=key)


def create(base: str, epochs: int, suffix: str, seed: int) -> None:
    client = _client()
    train_path, val_path = SFT_DIR / "train.jsonl", SFT_DIR / "val.jsonl"
    for path in (train_path, val_path):
        if not path.exists():
            raise SystemExit(f"{path} 없음 — 먼저 scripts/prepare_sft_data.py 실행")

    with train_path.open("rb") as f:
        train_file = client.files.create(file=f, purpose="fine-tune")
    with val_path.open("rb") as f:
        val_file = client.files.create(file=f, purpose="fine-tune")

    job = client.fine_tuning.jobs.create(
        model=base,
        training_file=train_file.id,
        validation_file=val_file.id,
        suffix=suffix,
        seed=seed,
        method={
            "type": "supervised",
            "supervised": {"hyperparameters": {"n_epochs": epochs}},
        },
    )
    line = (
        f"- {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC | job `{job.id}` | base `{base}` | "
        f"epochs {epochs} | seed {seed} | train {train_file.id} | val {val_file.id}"
    )
    with JOB_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"작업 생성: {job.id} (상태: {job.status})")
    print(f"확인: python -X utf8 scripts/finetune_counsel.py status {job.id}")


def status(job_id: str) -> None:
    client = _client()
    job = client.fine_tuning.jobs.retrieve(job_id)
    print(f"상태: {job.status} / 기반 모델: {job.model}")
    print(f"학습 토큰: {job.trained_tokens or '-'}")
    if job.fine_tuned_model:
        print(f"학습된 모델: {job.fine_tuned_model}")
    if job.error and job.error.message:
        print(f"오류: {job.error.message}")

    # 손실값 — 마지막 체크포인트 기준 (논문에 학습·검증 손실로 적는다)
    checkpoints = client.fine_tuning.jobs.checkpoints.list(job_id, limit=1).data
    if checkpoints:
        metrics = checkpoints[0].metrics
        print("마지막 체크포인트 지표:", json.dumps(metrics.model_dump(exclude_none=True), ensure_ascii=False))

    print("\n최근 이벤트:")
    for event in reversed(client.fine_tuning.jobs.list_events(job_id, limit=10).data):
        print(f"  {event.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="상담봇 SFT")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="파인튜닝 작업 생성")
    c.add_argument("--base", default="gpt-4o-2024-08-06")
    c.add_argument("--epochs", type=int, default=3)
    c.add_argument("--suffix", default="oddo-counsel")
    c.add_argument("--seed", type=int, default=42)
    s = sub.add_parser("status", help="작업 상태·손실값")
    s.add_argument("job_id")
    args = parser.parse_args()

    if args.cmd == "create":
        create(args.base, args.epochs, args.suffix, args.seed)
    else:
        status(args.job_id)


if __name__ == "__main__":
    main()