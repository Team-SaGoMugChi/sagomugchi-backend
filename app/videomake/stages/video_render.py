"""5. VideoRenderer — 승인된 컷 이미지를 first frame으로 Veo image-to-video 호출.

비동기 병렬 제출 + 단일 폴링 루프. 진입 즉시 승인 여부를 강제 확인한다.
승인 없이 Veo를 호출하는 경로가 코드상 존재해서는 안 된다 (컷당 약 $0.80).
"""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from pathlib import Path

from ..config import Settings
from ..errors import ProviderError, RenderTimeout
from ..job import JobStore
from ..models import Stage, Storyboard, VideoHandle
from ..prompts import PromptLibrary
from ..providers.base import VideoProvider

log = logging.getLogger(__name__)


async def render_cut_videos(
    sb: Storyboard,
    *,
    video: VideoProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    only: set[int] | None = None,
    force: bool = False,
) -> dict[int, Path]:
    targets = [c for c in sb.cuts if only is None or c.index in only]
    pending = [c for c in targets if force or not job.cut_video(c.index).exists()]
    cached = {
        c.index: job.cut_video(c.index) for c in targets if c not in pending
    }
    for idx in cached:
        log.info("컷 %d 영상 캐시 재사용", idx)
    if not pending:
        return cached

    # --- 승인 게이트. 여기를 통과하지 못하면 API를 부르지 않는다. ---
    job.assert_approved({c.index for c in pending})

    for cut in pending:
        if not job.cut_image(cut.index).exists():
            raise ProviderError(f"컷 {cut.index}의 시작 프레임 이미지가 없다")

    started = time.perf_counter()
    sem = asyncio.Semaphore(settings.video_concurrency)

    async def submit(cut) -> VideoHandle:
        async with sem:
            # 대사 컷은 화자마다 목소리 서술을 붙여야 전원이 같은 목소리로
            # 말하지 않는다. 인물 정의에서 찾아 붙인다.
            lines = [
                {
                    "speaker": line.speaker,
                    "text": line.text,
                    "voice": getattr(sb.character(line.speaker), "voice", ""),
                }
                for line in cut.dialogue
            ]
            motion = prompts.render(
                "motion.j2", motion_prompt=cut.motion_prompt, dialogue=lines
            )
            handle = await video.submit(
                cut_index=cut.index,
                motion_prompt=motion,
                first_frame=job.cut_image(cut.index),
                negative_prompt=(
                    prompts.video_negative_prompt_dialogue
                    if cut.is_dialogue
                    else prompts.video_negative_prompt
                ),
                aspect_ratio=settings.aspect_ratio,
                resolution=settings.video_resolution,
                duration_seconds=cut.duration_seconds,
                generate_audio=cut.is_dialogue,
            )
        job.cut_handle(cut.index).write_text(
            handle.model_dump_json(indent=2), encoding="utf-8"
        )
        log.info("컷 %d 제출됨: %s", cut.index, handle.operation_name)
        return handle

    # 이미 제출된 컷은 절대 다시 제출하지 않는다. 재제출하면 그만큼 다시 과금된다.
    handles: list[VideoHandle] = []
    to_submit = []
    for cut in pending:
        hp = job.cut_handle(cut.index)
        if hp.exists() and not force:
            h = VideoHandle.model_validate_json(hp.read_text(encoding="utf-8"))
            log.info("컷 %d: 진행 중인 작업을 이어받는다 (%s)", cut.index, h.operation_name)
            handles.append(h)
        else:
            to_submit.append(cut)

    errors: list[str] = []
    # 일부 제출이 실패해도 성공한 것들은 끝까지 회수한다.
    submitted = await asyncio.gather(
        *(submit(c) for c in to_submit), return_exceptions=True
    )
    for cut, outcome in zip(to_submit, submitted):
        if isinstance(outcome, BaseException):
            errors.append(f"컷 {cut.index} 제출 실패: {outcome}")
            log.error("컷 %d 제출 실패: %s", cut.index, outcome)
        else:
            handles.append(outcome)

    results = dict(cached)
    remaining = {h.cut_index: h for h in handles}
    deadline = time.monotonic() + settings.poll_timeout_seconds

    while remaining:
        if time.monotonic() > deadline:
            raise RenderTimeout(
                f"컷 {sorted(remaining)}이 {settings.poll_timeout_seconds:.0f}초 안에 "
                "완료되지 않았다. 핸들은 job 디렉터리에 저장되어 있다."
            )
        await asyncio.sleep(settings.poll_interval_seconds)
        statuses = await asyncio.gather(
            *(video.poll(h) for h in remaining.values())
        )
        for handle, status in zip(list(remaining.values()), statuses):
            if not status.done:
                continue
            remaining.pop(handle.cut_index)
            if status.failed:
                errors.append(f"컷 {handle.cut_index}: {status.error}")
                log.error("컷 %d 실패: %s", handle.cut_index, status.error)
                continue
            dest = job.cut_video(handle.cut_index)
            await video.fetch(handle, dest)
            cut = sb.cut(handle.cut_index)
            cost = video.price_per_second(settings.video_resolution) * cut.duration_seconds
            job.record_cost(f"cut{handle.cut_index}_video", Decimal(cost))
            results[handle.cut_index] = dest
            log.info(
                "컷 %d 완료 — %s ($%.2f)", handle.cut_index, dest.name, cost
            )
        log.info("대기 중인 컷: %s", sorted(remaining) or "없음")

    job.record_stage(
        Stage.VIDEOS,
        elapsed_s=time.perf_counter() - started,
        cuts=sorted(results),
        errors=errors,
    )
    if errors:
        raise ProviderError(
            "일부 컷 렌더 실패 (성공한 컷은 캐시되어 재렌더되지 않는다):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
    return results
