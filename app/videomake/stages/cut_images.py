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
    # 장소마다 처음 나오는 컷. 이 컷을 먼저 그리고, 같은 장소의 나머지 컷은 이 그림을
    # 장소 기준으로 받는다. 컷마다 따로 그리면 같은 강의실이 매번 다른 방이 된다.
    anchors: dict[str, int] = {}
    for c in sb.cuts:
        if c.location is not None:
            anchors.setdefault(c.location, c.index)
    started = time.perf_counter()

    async def one(cut) -> tuple[int, Path]:
        dest = job.cut_image(cut.index)
        if dest.exists() and not force:
            log.info("컷 %d 이미지 캐시 재사용", cut.index)
            return cut.index, dest
        # 같은 장소의 첫 컷 그림을 장소 기준으로 함께 넘긴다(그 컷 자신은 제외).
        anchor = anchors.get(cut.location)
        place_ref = (
            job.cut_image(anchor)
            if anchor is not None and anchor != cut.index and job.cut_image(anchor).exists()
            else None
        )
        prompt = prompts.render(
            "cut_image.j2",
            location=sb.location(cut.location),
            same_place=place_ref is not None,
            name=sb.protagonist.name,
            image_prompt=cut.image_prompt,
            camera_distance=cut.camera_distance,
            aspect_ratio=settings.aspect_ratio,
            style_block=prompts.style_block,
            mood_block=prompts.render(
                "mood.j2", mood=cut.mood, name=sb.protagonist.name, part="image"
            ),
        )
        async with sem:
            result = await image.generate(
                prompt=prompt,
                dest=dest,
                references=[sheet, place_ref] if place_ref else [sheet],
                aspect_ratio=settings.aspect_ratio,
                image_size=settings.image_size,
            )
        log.info("컷 %d 이미지 %.1fs / $%s", cut.index, result.elapsed_s, result.cost_usd)
        job.record_cost(f"cut{cut.index}_image", result.cost_usd)
        # 이미지를 새로 뽑았으면 기존 승인은 무효다.
        job.unapprove({cut.index})
        return cut.index, dest

    first = [c for c in targets if anchors.get(c.location) in (None, c.index)]
    rest = [c for c in targets if c not in first]
    pairs = await asyncio.gather(*(one(c) for c in first))
    pairs += await asyncio.gather(*(one(c) for c in rest))
    job.record_stage(
        Stage.CUT_IMAGES,
        elapsed_s=time.perf_counter() - started,
        cuts=[i for i, _ in pairs],
    )
    return dict(pairs)
