"""6. NarrationSynthesizer — 한국어 TTS.

Veo 네이티브 오디오에 맡기지 않는다. Veo는 영상만 담당하고 나레이션은 여기서
따로 만들어 Compositor에서 믹싱한다.
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
from ..providers.base import TTSProvider

log = logging.getLogger(__name__)


async def synthesize_narrations(
    sb: Storyboard,
    *,
    tts: TTSProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    only: set[int] | None = None,
    force: bool = False,
    concurrency: int = 3,
) -> dict[int, Path]:
    # 대사 컷은 Veo가 직접 발화한다. 여기서 만들 나레이션이 없다.
    targets = [
        c
        for c in sb.cuts
        if (only is None or c.index in only) and not c.is_dialogue
    ]
    sem = asyncio.Semaphore(concurrency)
    started = time.perf_counter()

    async def one(cut) -> tuple[int, Path]:
        dest = job.cut_narration(cut.index)
        if dest.exists() and not force:
            log.info("컷 %d 나레이션 캐시 재사용", cut.index)
            return cut.index, dest
        style = prompts.render("narration_style.j2", text=cut.narration)
        async with sem:
            result = await tts.synthesize(
                text=cut.narration,
                dest=dest,
                voice=settings.tts_voice,
                style_prompt=style,
            )
        job.record_cost(f"cut{cut.index}_tts", result.cost_usd)
        if result.duration_s > cut.duration_seconds:
            # 컷보다 길면 Compositor에서 잘린다. 스토리보드 글자수를 줄여야 한다.
            log.warning(
                "컷 %d 나레이션이 %.1fs로 컷 길이 %ds를 넘는다. 뒷부분이 잘린다.",
                cut.index, result.duration_s, cut.duration_seconds,
            )
        else:
            log.info("컷 %d 나레이션 %.1fs", cut.index, result.duration_s)
        return cut.index, dest

    pairs = await asyncio.gather(*(one(c) for c in targets))
    job.record_stage(
        Stage.NARRATION,
        elapsed_s=time.perf_counter() - started,
        cuts=[i for i, _ in pairs],
    )
    return dict(pairs)
