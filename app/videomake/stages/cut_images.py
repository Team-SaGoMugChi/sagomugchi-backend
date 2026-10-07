"""3. CutImageGenerator — 캐릭터 시트·장소 시트를 레퍼런스로 컷별 시작 프레임 생성.

반복과 검수는 전부 여기서 끝낸다. 컷 이미지 1장은 약 $0.045, 영상 1컷은 $0.80이다.
이미지를 17번 다시 뽑아도 영상 1컷보다 싸다.

레퍼런스는 그 컷 화면에 보이는 인물의 캐릭터 시트(위치 순서대로)와 그 장소의 장소 시트다.
같은 장소 컷의 첫 그림을 넘기던 방식은 그림 모델이 시점까지 베껴 폐기했다(reference_sheets.py).
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from ..config import Settings
from ..job import JobStore
from ..models import Cut, Stage, Storyboard
from ..prompts import PromptLibrary
from ..providers.base import ImageProvider

log = logging.getLogger(__name__)

_POSITION_ORDER = {"left": 0, "center": 1, "right": 2}


async def generate_cut_images(
    sb: Storyboard,
    *,
    sheet: Path,
    image: ImageProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    character_sheets: dict[str, Path] | None = None,
    location_sheets: dict[str, Path] | None = None,
    only: set[int] | None = None,
    force: bool = False,
) -> dict[int, Path]:
    """sheet: 주인공 캐릭터 시트. character_sheets: 조연 이름 → 시트. location_sheets: 장소 이름 → 시트."""
    sheets = {sb.protagonist.name: sheet, **(character_sheets or {})}
    location_sheets = location_sheets or {}
    targets = [c for c in sb.cuts if only is None or c.index in only]
    sem = asyncio.Semaphore(settings.image_concurrency)
    started = time.perf_counter()

    async def one(cut) -> tuple[int, Path]:
        dest = job.cut_image(cut.index)
        if dest.exists() and not force:
            log.info("컷 %d 이미지 캐시 재사용", cut.index)
            return cut.index, dest
        prompt, references = cut_image_request(
            sb,
            cut,
            sheets=sheets,
            location_sheets=location_sheets,
            prompts=prompts,
            aspect_ratio=settings.aspect_ratio,
        )
        async with sem:
            result = await image.generate(
                prompt=prompt,
                dest=dest,
                references=references,
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


def cut_image_request(
    sb: Storyboard,
    cut: Cut,
    *,
    sheets: dict[str, Path],
    location_sheets: dict[str, Path],
    prompts: PromptLibrary,
    aspect_ratio: str,
    camera_distance: str | None = None,
    thumbnail: bool = False,
) -> tuple[str, list[Path]]:
    """컷 하나를 그릴 프롬프트와 레퍼런스(화면 속 인물 시트 → 장소 시트).

    컷 그림과 썸네일(가로 구도)이 같은 규칙으로 그려지도록 한곳에 둔다.
    """
    cast = sorted(sb.visible_cast(cut), key=lambda m: _POSITION_ORDER[m.position])
    people = [m for m in cast if m.name in sheets]
    place_sheet = location_sheets.get(cut.location)
    references = [sheets[m.name] for m in people] + ([place_sheet] if place_sheet else [])
    prompt = prompts.render(
        "cut_image.j2",
        people=people,
        cast=cast,
        location=sb.location(cut.location),
        has_location_sheet=place_sheet is not None,
        thumbnail=thumbnail,
        image_prompt=cut.image_prompt,
        camera_distance=camera_distance or cut.camera_distance,
        aspect_ratio=aspect_ratio,
        style_block=prompts.style_block,
        mood_block=prompts.render(
            "mood.j2", mood=cut.mood, name=sb.protagonist.name, part="image"
        ),
    )
    return prompt, references
