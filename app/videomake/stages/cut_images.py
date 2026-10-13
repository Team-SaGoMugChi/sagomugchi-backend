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


def voice_off_screen(sb: Storyboard, cut: Cut) -> bool:
    """대사 컷인데 말하는 사람이 모두 화면에 없다(전화 속 목소리 등).

    이런 컷은 Veo에게 말소리를 시키지 않는다 — 말소리를 만들면 화면에 보이는 사람의 입을
    그 소리에 맞춰 움직였다(듣기만 해야 하는 사람이 말하는 것처럼 보임). 목소리는 더빙이 넣는다."""
    if not cut.is_dialogue:
        return False
    shown = {m.name for m in sb.visible_cast(cut)}
    return all(line.speaker not in shown for line in cut.dialogue)


def mood_subject(sb: Storyboard, cut: Cut) -> str:
    """감정(표정·자세) 지시를 받을 사람 — 그 컷 화면에 보이는 사람. 주인공이 보이면 주인공,
    주인공 없이 다른 사람만 보이면 그 사람이다. 아무도 없으면 주인공(장면 분위기).
    늘 주인공 이름을 쓰면 지수 혼자 나오는 컷에 "민서: hurt"처럼 화면에 없는 사람을 지시했다."""
    names = [m.name for m in sb.visible_cast(cut)]
    if not names or sb.protagonist.name in names:
        return sb.protagonist.name
    return names[0]


def solo_listener_side(sb: Storyboard, cut: Cut, cast: list) -> str | None:
    """대사 컷에 말하는 사람 혼자 보이면, 화면 밖 상대가 있는 쪽(시선 방향). 아니면 None.
    화면 왼쪽에 있는 사람은 오른쪽을 본다. 가운데면 오른쪽으로 둔다.

    상대가 그 장소에 실제로 있을 때만이다 — 같은 장소의 다른 컷에 다른 사람이 함께 보인다.
    전화 통화처럼 혼자 있는 장면에 "화면 밖 상대"를 쓰면 그림 모델이 화면 끝에 엉뚱한
    사람의 뒷모습을 그렸다."""
    if not cut.is_dialogue or len(cast) != 1:
        return None
    speaker = cast[0].name
    if speaker not in {line.speaker for line in cut.dialogue}:
        return None
    present = any(
        m.name != speaker
        for c in sb.cuts
        if c.location == cut.location
        for m in c.cast
    )
    if not present:
        return None
    return "left" if cast[0].position == "right" else "right"


def moment_shot(sb: Storyboard, cut: Cut) -> int | None:
    """혼자 나오는 대사 컷이 참고할 같은 순간의 컷 — 같은 장소에서 말하는 사람이 다른 사람과
    함께 보이는 가장 가까운 컷(앞 컷 우선). 테이블·의자·컵·옷을 맞추는 데만 쓴다.
    텍스트만으로는 한 사람 컷의 테이블 모양·색이 두 사람 컷과 달라졌다."""
    if solo_listener_side(sb, cut, sb.visible_cast(cut)) is None:
        return None
    speaker = cut.cast[0].name
    candidates = [
        c for c in sb.cuts
        if c.index != cut.index and c.location == cut.location
        and len(c.cast) > 1 and speaker in {m.name for m in c.cast}
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c.index > cut.index, abs(c.index - cut.index))).index


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
        solo_side=solo_listener_side(sb, cut, cast),
        location=sb.location(cut.location),
        has_location_sheet=place_sheet is not None,
        has_moment_image=moment_image is not None,
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
