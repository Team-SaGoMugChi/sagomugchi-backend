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
import shutil
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

    async def make(dest: Path, prompt: str, aspect: str, label: str, references: list[Path] | None = None) -> Path:
        if dest.exists() and not force:
            log.info("%s 캐시 재사용", label)
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with sem:
            result = await image.generate(
                prompt=prompt, dest=dest, aspect_ratio=aspect, image_size=settings.image_size,
                **({"references": references} if references else {}),
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
    async def make_location(i: int, loc) -> Path:
        """기준 장면(입구에서 본 빈 장소) 1장을 먼저 그리고, 그것을 참고로 네 방향 시트를 그린다.

        네 방향을 한 장에 한꺼번에 그리면 판마다 책상 수가 다르거나 방이 좌우로 뒤집혔다(2026-11 카페).
        뉴테이크의 실사 워크플로처럼 "기준 장면 → 그 장면을 참고한 다른 시점" 순서로 그린다.
        시트 왼쪽 위 칸이 기준 장면과 같은 방인지, 좌우가 뒤집히지 않았는지 특징점으로 확인한다."""
        dest = job.location_sheet(i)
        if dest.exists() and not force:
            log.info("location_sheet %s 캐시 재사용", loc.name)
            return dest
        text = prompts.render("location_sheet.j2", description=loc.description, floor_plan=loc.floor_plan,
                              style_block=prompts.style_block)
        master = dest.with_name(f"master_{dest.name}")
        try:
            await make(master, prompts.render("location_master.j2", description=loc.description,
                                              floor_plan=loc.floor_plan, style_block=prompts.style_block),
                       "1:1", f"location_master {loc.name}")
        except Exception as exc:  # 기준 장면이 없으면 예전처럼 시트만 그린다
            log.warning("장소 %s 기준 장면을 그리지 못해 시트만 그린다: %s", loc.name, exc)
            return await make(dest, text, "1:1", f"location_sheet {loc.name}")
        base = prompts.render("location_sheet.j2", description=loc.description, floor_plan=loc.floor_plan,
                              style_block=prompts.style_block, has_master=True)
        text, tries = base, []
        for attempt in range(1, settings.image_check_retries + 2):
            target = dest.with_name(f"{dest.stem}_try{attempt}.png")
            await make(target, text, "1:1", f"location_sheet {loc.name} try{attempt}", references=[master])
            same, flipped = await asyncio.to_thread(master_panel_match, master, target)
            tries.append(((same or 0) - (flipped or 0), target))
            if same is None or (same >= MASTER_MIN_MATCH and same > flipped):
                break
            problem = ("its top-left panel is the master view MIRRORED left to right" if flipped >= same
                       else "its top-left panel is not the master view")
            log.warning("장소 %s 시트 다시 그림(%d): %s (맞는 점 %s, 뒤집으면 %s)", loc.name, attempt, problem, same, flipped)
            text = base + f"\n\nTHE PREVIOUS SHEET WAS WRONG: {problem}. The top-left panel must be exactly the attached master view."
        shutil.copy2(max(tries, key=lambda t: t[0])[1], dest)
        return dest

    location_jobs = [
        make_location(i, loc)
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


MASTER_MIN_MATCH = 30  # 시트 왼쪽 위 칸과 기준 장면이 이만큼은 맞아야 같은 방이다(cut_images.PLATE_MIN_MATCH와 같은 기준)


def master_panel_match(master: Path, sheet: Path) -> tuple[int | None, int | None]:
    """(시트 왼쪽 위 칸과 기준 장면의 맞는 점, 그 칸을 좌우로 뒤집었을 때의 맞는 점). 읽지 못하면 (None, None)."""
    from PIL import Image, ImageOps

    from .cut_images import plate_match

    try:
        im = Image.open(sheet)
        w, h = im.size
        panel = im.crop((0, 0, w // 2, h // 2))
        straight = sheet.with_name(f"{sheet.stem}_panel.png")
        mirrored = sheet.with_name(f"{sheet.stem}_panel_flip.png")
        panel.save(straight)
        ImageOps.mirror(panel).save(mirrored)
    except Exception as exc:
        log.warning("장소 시트 확인 실패: %s", exc)
        return None, None
    same, flipped = plate_match(master, straight), plate_match(master, mirrored)
    if not same and not flipped:  # 특징점이 아예 없으면(무늬 없는 그림) 판단하지 않는다
        return None, None
    return same, flipped
