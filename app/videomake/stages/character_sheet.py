"""2. CharacterSheetBuilder — job당 1회 생성 후 모든 컷의 레퍼런스로 재사용.

컷 간 일관성은 전적으로 이 시트에 달려 있다. Veo Developer API에는 seed가 없어서
영상 단계에 재현성 안전망이 없기 때문이다.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from ..config import Settings
from ..job import JobStore
from ..models import Stage, Storyboard
from ..prompts import PromptLibrary
from ..providers.base import ImageProvider

log = logging.getLogger(__name__)


async def build_character_sheet(
    sb: Storyboard,
    *,
    image: ImageProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    force: bool = False,
) -> Path:
    dest = job.character_sheet_path
    if dest.exists() and not force:
        log.info("캐릭터 시트 캐시 재사용: %s", dest)
        return dest

    prompt = prompts.render(
        "character_sheet.j2",
        name=sb.protagonist.name,
        appearance=sb.protagonist.appearance,
        style_block=prompts.style_block,
    )
    started = time.perf_counter()
    # 시트는 세 뷰를 나란히 놓으므로 가로 구도가 유리하다.
    result = await image.generate(
        prompt=prompt,
        dest=dest,
        aspect_ratio="16:9",
        image_size=settings.image_size,
    )
    log.info("캐릭터 시트 생성 %.1fs / $%s", result.elapsed_s, result.cost_usd)
    job.record_cost("character_sheet", result.cost_usd)
    job.record_stage(
        Stage.CHARACTER_SHEET, elapsed_s=time.perf_counter() - started, path=str(dest)
    )
    return dest
