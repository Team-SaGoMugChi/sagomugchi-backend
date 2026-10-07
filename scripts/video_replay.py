"""같은 일기로 영상 생성만 다시 돌린다: python -m scripts.video_replay <작업ID|폴더|input.json>

영상 로직(스토리보드 프롬프트·길이 규칙 등)을 고친 뒤 앱에서 일기를 새로 쓰지 않고, 이미 만든
영상 작업의 입력(input.json — 일기 글·감정·일기 전달 JSON)을 그대로 넣어 결과를 비교한다.
결과는 새 작업 폴더(.cache/videomake/jobs/replay-…)에 남는다. 일기가 들어 있으므로 커밋하지 않는다.

    --list                       최근 영상 작업 목록
    --until storyboard (기본)     시나리오만. GPT 호출 한 번(수 센트)
    --until images               캐릭터 시트·컷 그림까지(그림당 약 $0.045). review.html로 확인
    --until video                최종 mp4까지
    --media dummy                시나리오만 진짜, 그림·영상·나레이션은 더미(과금 거의 0).
                                 컷 길이·흐름이 담긴 mp4를 앱 없이 확인할 때
    --yes                        실제 영상 렌더 전 비용 확인을 건너뛴다
    --save-to 폴더                완성된 mp4와 시나리오 요약(txt)을 이 폴더에 복사한다

.env의 VIDEOMAKE_DUMMY와 상관없이 시나리오는 항상 실제 LLM(.env의 VIDEOMAKE_LLM_PROVIDER)으로 짠다.
"""

import argparse
import asyncio
import json
import shutil
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.videomake.config import Settings, get_settings
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput, Storyboard
from app.videomake.pipeline import Pipeline
from app.videomake.providers.registry import Providers, build_fake_providers, build_llm, build_providers

STAGES = ("storyboard", "images", "video")


def load_input(source: str, jobs_dir: Path) -> DiaryInput:
    """작업 ID, 작업 폴더, input.json 경로 중 무엇이든 받는다."""
    path = Path(source)
    if not path.exists():
        path = jobs_dir / source
    if path.is_dir():
        path = path / "input.json"
    if not path.exists():
        raise SystemExit(f"입력을 찾지 못했어요: {source} (작업 ID는 --list로 확인)")
    return DiaryInput.model_validate_json(path.read_text(encoding="utf-8"))


def new_job(jobs_dir: Path, name: str | None) -> JobStore:
    job_id = "replay-" + datetime.now().strftime("%m%d-%H%M%S") + (f"-{name}" if name else "")
    return JobStore(jobs_dir, job_id)


def _real_llm(settings: Settings):
    client = None
    if settings.llm_provider == "gemini":
        from google import genai

        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
    return build_llm(settings, client)


def build_replay_providers(settings: Settings, *, media: str) -> Providers:
    """시나리오는 항상 실제 LLM. 그림·영상·나레이션은 media에 따라 실제 또는 더미."""
    if media == "real":
        return build_providers(settings.model_copy(update={"dummy": False}))
    fake = build_fake_providers(settings)
    return Providers(
        llm=_real_llm(settings),
        image=fake.image,
        video=fake.video,
        tts=fake.tts,
        client=None,
        video_client=None,
    )


def summary(sb: Storyboard, job: JobStore) -> str:
    lengths = [c.duration_seconds for c in sb.cuts]
    lines = [
        f"작업: {job.dir}",
        f"주인공: {sb.protagonist.name}",
        f"컷 {len(sb.cuts)}개 · 길이 {lengths} · 합계 {sb.total_seconds}초",
    ]
    for c in sb.cuts:
        voice = c.narration or " / ".join(f"{line.speaker}: {line.text}" for line in c.dialogue)
        lines.append(f"  {c.index:>2}. {c.duration_seconds}초 {c.mood} {c.location or '-'} {c.camera_distance:<6} | {voice}")
    for d in sb.distortions:
        lines.append(f"  인지왜곡: {d.fact} → {d.felt_as} ({d.kind})")
    lines.append(f"지금까지 비용: ${job.spent_usd():.3f}")
    return "\n".join(lines)


def _ask(estimate, limit: Decimal) -> bool:
    print(f"\n실제 영상 렌더 예상 비용 ${estimate.total_usd:.2f} (상한 ${limit:.2f})")
    return input("렌더할까요? [y/N] ").strip().lower() == "y"


async def replay(
    diary: DiaryInput,
    *,
    pipe: Pipeline,
    until: str,
    confirm=None,
) -> Storyboard:
    sb = await pipe.plan(diary)
    if until == "storyboard":
        return sb
    await pipe.build_images(sb)
    if until == "images":
        return sb
    if confirm is not None and not confirm(pipe.estimate(sb), pipe.settings.max_cost_usd):
        raise SystemExit("렌더를 취소했어요. 시나리오와 그림은 작업 폴더에 남아 있어요.")
    pipe.approve(sb)
    await pipe.finish(sb)
    return sb


def save_copy(sb: Storyboard, job: JobStore, folder: Path) -> Path:
    """완성 영상을 보기 쉬운 곳에 둔다. 이름에 작업 ID·컷 수·길이를 넣어 여러 번 돌려도 비교된다."""
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{job.dir.name}_{len(sb.cuts)}컷_{sb.total_seconds}초"
    dest = folder / f"{stem}.mp4"
    shutil.copy2(job.final_path, dest)
    (folder / f"{stem}.txt").write_text(summary(sb, job) + "\n", encoding="utf-8")
    return dest


def list_jobs(jobs_dir: Path, limit: int = 15) -> None:
    jobs = sorted(
        (p for p in jobs_dir.glob("*") if (p / "input.json").exists()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    for p in jobs:
        sb_path = p / "storyboard.json"
        length = ""
        if sb_path.exists():
            cuts = json.loads(sb_path.read_text(encoding="utf-8")).get("cuts", [])
            length = f"컷 {len(cuts)}개 {sum(c.get('duration_seconds', 0) for c in cuts)}초"
        handoff = "handoff O" if json.loads((p / "input.json").read_text(encoding="utf-8")).get("handoff") else "handoff X"
        done = "mp4 O" if (p / "final.mp4").exists() else ""
        when = datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M")
        print(f"{when}  {p.name}  {handoff}  {length}  {done}")


def main() -> None:
    parser = argparse.ArgumentParser(description="같은 일기로 영상 생성만 다시 돌린다.")
    parser.add_argument("source", nargs="?", help="작업 ID, 작업 폴더 또는 input.json")
    parser.add_argument("--list", action="store_true", help="최근 영상 작업 목록")
    parser.add_argument("--until", choices=STAGES, default="storyboard")
    parser.add_argument("--media", choices=("real", "dummy"), default="real")
    parser.add_argument("--name", help="새 작업 폴더 이름 뒤에 붙일 메모(영문·숫자)")
    parser.add_argument("--yes", action="store_true", help="실제 렌더 전 비용 확인 생략")
    parser.add_argument("--save-to", type=Path, help="완성 mp4·요약을 복사할 폴더")
    args = parser.parse_args()

    settings = get_settings()
    if args.list or not args.source:
        list_jobs(settings.jobs_dir)
        return

    diary = load_input(args.source, settings.jobs_dir)
    job = new_job(settings.jobs_dir, args.name)
    pipe = Pipeline(
        providers=build_replay_providers(settings, media=args.media),
        job=job,
        settings=settings,
    )
    paid_render = args.until == "video" and args.media == "real"
    confirm = None if args.yes or not paid_render else _ask
    print(f"입력: {args.source} → 새 작업 {job.dir.name} (단계: {args.until}, 그림·영상: {args.media})")

    started = time.perf_counter()
    sb = asyncio.run(replay(diary, pipe=pipe, until=args.until, confirm=confirm))
    print()
    print(summary(sb, job))
    if args.until == "images":
        print(f"그림 확인: {job.review_path}")
    if args.until == "video":
        print(f"영상: {job.final_path}")
        if args.save_to:
            print(f"복사: {save_copy(sb, job, args.save_to.expanduser())}")
    print(f"걸린 시간: {time.perf_counter() - started:.0f}초")


if __name__ == "__main__":
    main()
