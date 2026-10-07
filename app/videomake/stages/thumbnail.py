"""8. 대표 장면 썸네일 — 앱 홈 영상 카드(가로 16:9)에 보여줄 그림 한 장.

영상과 컷 그림은 세로(9:16)라 가로 카드에 넣으면 인물이 손톱만 해지거나 잘린다. 그래서
대표 컷과 같은 장면을 같은 캐릭터·장소 시트로 **가로 구도로 한 장 더** 그린다.
영상 렌더와 동시에 그려 기다리는 시간은 늘지 않는다. 그림 1장 비용(약 $0.045).

대표 컷: 영상의 대표 감정과 같은 mood의 컷 → 없으면 평온이 아닌 컷 → 없으면 가운데 컷.
같은 조건이면 목소리(나레이션·대사)가 있고 긴 컷 — 이야기의 핵심 순간일 가능성이 높다.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from ..config import Settings
from ..errors import VideomakeError
from ..job import JobStore
from ..models import Cut, Storyboard
from ..prompts import PromptLibrary
from ..providers.base import ImageProvider
from .cut_images import cut_image_request

log = logging.getLogger(__name__)

THUMBNAIL_ASPECT = "16:9"
THUMBNAIL_WIDTH = 960  # 앱 카드(약 340dp × 3배)에 충분하고 용량은 100KB 안팎
# 홈 카드는 작아서 컷 그대로의 거리(wide/full)면 인물이 손톱만 하다. 중거리로 당긴다.
THUMBNAIL_DISTANCE = "medium"


def representative_cut(sb: Storyboard, primary_emotion: str | None) -> Cut:
    def weight(c: Cut) -> tuple[bool, int]:
        return (not c.is_silent, c.duration_seconds)

    same = [c for c in sb.cuts if primary_emotion and c.mood == primary_emotion]
    if same:
        return max(same, key=weight)
    moving = [c for c in sb.cuts if c.mood != "평온"]
    if moving:
        return max(moving, key=weight)
    return sb.cuts[len(sb.cuts) // 2]


async def build_thumbnail(
    sb: Storyboard,
    *,
    primary_emotion: str | None,
    sheets: dict[str, Path],
    location_sheets: dict[str, Path],
    image: ImageProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    force: bool = False,
) -> Path:
    dest = job.thumbnail_path
    if dest.exists() and not force:
        log.info("썸네일 캐시 재사용")
        return dest
    cut = representative_cut(sb, primary_emotion)
    prompt, references = cut_image_request(
        sb,
        cut,
        sheets=sheets,
        location_sheets=location_sheets,
        prompts=prompts,
        aspect_ratio=THUMBNAIL_ASPECT,
        camera_distance=THUMBNAIL_DISTANCE,
        thumbnail=True,
    )
    started = time.perf_counter()
    raw = job.dir / "thumbnail_raw.png"
    result = await image.generate(
        prompt=prompt,
        dest=raw,
        references=references,
        aspect_ratio=THUMBNAIL_ASPECT,
        image_size=settings.image_size,
    )
    job.record_cost("thumbnail", result.cost_usd)
    _to_jpeg(raw, dest)
    log.info(
        "썸네일: 컷 %d(%s) %.1fs / $%s",
        cut.index, cut.mood, time.perf_counter() - started, result.cost_usd,
    )
    return dest


def _to_jpeg(src: Path, dest: Path) -> None:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise VideomakeError("ffmpeg를 찾을 수 없다. `brew install ffmpeg`")
    proc = subprocess.run(
        [exe, "-y", "-i", str(src), "-vf", f"scale={THUMBNAIL_WIDTH}:-2", "-q:v", "3", str(dest)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise VideomakeError("썸네일 변환 실패:\n" + proc.stderr.strip()[-500:])
