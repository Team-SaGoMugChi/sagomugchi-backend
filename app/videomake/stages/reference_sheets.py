"""2-b. 조연 캐릭터 시트 + 장소 시트 — 주인공 캐릭터 시트처럼 job당 1회 만들어 컷 그림에 넘긴다.

- 조연 시트: 화면에 한 번이라도 나오는 조연만(Storyboard.on_screen_supporting). 없으면 컷마다
  얼굴·옷이 바뀐다.
- 장소 시트: 같은 장소를 네 방향에서 본 그림 한 장. 같은 장소 컷의 첫 그림을 기준으로 넘기면
  그림 모델이 보는 방향까지 베껴 모든 컷이 같은 벽만 비췄다(2026-10 관측). 여러 방향을 함께
  보여주면 방은 같게, 시점은 컷마다 다르게 그린다.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..config import Settings
from ..job import JobStore
from ..models import Storyboard
from ..prompts import PromptLibrary
from ..providers.base import ImageProvider

log = logging.getLogger(__name__)


async def build_reference_sheets(
    sb: Storyboard,
    *,
    image: ImageProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    force: bool = False,
) -> tuple[dict[str, Path], dict[str, Path]]:
    """(조연 이름 → 시트, 장소 이름 → 시트)."""
    sem = asyncio.Semaphore(settings.image_concurrency)

    async def make(dest: Path, prompt: str, aspect: str, label: str) -> Path:
        if dest.exists() and not force:
            log.info("%s 캐시 재사용", label)
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with sem:
            result = await image.generate(
                prompt=prompt, dest=dest, aspect_ratio=aspect, image_size=settings.image_size
            )
        log.info("%s 생성 %.1fs / $%s", label, result.elapsed_s, result.cost_usd)
        job.record_cost(label, result.cost_usd)
        return dest

    supporting = sb.on_screen_supporting
    character_jobs = [
        make(
            job.supporting_sheet(sb.supporting.index(c) + 1),
            prompts.render(
                "character_sheet.j2",
                name=c.name,
                appearance=c.appearance,
                style_block=prompts.style_block,
            ),
            "16:9",
            f"character_sheet {c.name}",
        )
        for c in supporting
    ]
    location_jobs = [
        make(
            job.location_sheet(i),
            prompts.render(
                "location_sheet.j2", description=loc.description, style_block=prompts.style_block
            ),
            "1:1",
            f"location_sheet {loc.name}",
        )
        for i, loc in enumerate(sb.locations, start=1)
        if any(c.location == loc.name for c in sb.cuts)
    ]
    character_paths = await asyncio.gather(*character_jobs)
    location_paths = await asyncio.gather(*location_jobs)
    used_locations = [loc for loc in sb.locations if any(c.location == loc.name for c in sb.cuts)]
    return (
        {c.name: p for c, p in zip(supporting, character_paths)},
        {loc.name: p for loc, p in zip(used_locations, location_paths)},
    )
