"""3. CutImageGenerator — 캐릭터 시트를 레퍼런스로 컷별 시작 프레임 생성.

반복과 검수는 전부 여기서 끝낸다. 컷 이미지 1장은 약 $0.045, 영상 1컷은 $0.80이다.
이미지를 17번 다시 뽑아도 영상 1컷보다 싸다.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from ..config import Settings
from ..job import JobStore
from ..models import Stage, Storyboard
from ..prompts import PromptLibrary
from ..providers.base import ImageProvider

log = logging.getLogger(__name__)


async def generate_cut_images(
    sb: Storyboard,
    *,
    sheet: Path,
    image: ImageProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    only: set[int] | None = None,
    force: bool = False,
) -> dict[int, Path]:
    targets = [c for c in sb.cuts if only is None or c.index in only]
    sem = asyncio.Semaphore(settings.image_concurrency)
    started = time.perf_counter()

    async def one(cut) -> tuple[int, Path]:
        dest = job.cut_image(cut.index)
        if dest.exists() and not force:
            log.info("컷 %d 이미지 캐시 재사용", cut.index)
            return cut.index, dest
        prompt = prompts.render(
            "cut_image.j2",
            name=sb.protagonist.name,
            image_prompt=cut.image_prompt,
            camera_distance=cut.camera_distance,
            aspect_ratio=settings.aspect_ratio,
            style_block=prompts.style_block,
        )
        async with sem:
            result = await image.generate(
                prompt=prompt,
                dest=dest,
                references=[sheet],
                aspect_ratio=settings.aspect_ratio,
                image_size=settings.image_size,
            )
        log.info("컷 %d 이미지 %.1fs / $%s", cut.index, result.elapsed_s, result.cost_usd)
        job.record_cost(f"cut{cut.index}_image", result.cost_usd)
        # 이미지를 새로 뽑았으면 기존 승인은 무효다.
        job.unapprove({cut.index})
        return cut.index, dest

    pairs = await asyncio.gather(*(one(c) for c in targets))
    job.record_stage(
        Stage.CUT_IMAGES,
        elapsed_s=time.perf_counter() - started,
        cuts=[i for i, _ in pairs],
    )
    return dict(pairs)
