"""더미 provider. GCP 인증·과금 없이 파이프라인 전체를 돌린다.

`VIDEOMAKE_DUMMY=true`일 때 registry가 실제 provider 대신 이걸 조립한다.
Vertex ADC가 없는 팀원도 앱 Step3 흐름(작업 등록 → 진행률 → mp4 재생)을
끝까지 확인할 수 있게 하기 위한 것이다. ffmpeg로 실제 png/mp4/wav를 만들기
때문에 Compositor까지 진짜로 돌아가고, 결과 영상도 앱에서 재생된다.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import wave
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from ..models import AudioResult, ImageResult, VideoHandle, VideoResult, VideoStatus
from .base import LLMResult

T = TypeVar("T", bound=BaseModel)

# 호출마다 잠깐 멈춘다. 즉시 끝나면 앱 로딩 화면의 진행률을 확인할 수 없다.
STEP_DELAY_SECONDS = 0.5

# 4초 컷 상한(14자) 안에 든다.
_NARRATIONS = [
    "회의실에 그만 남았어요.",
    "빛이 천천히 기울었어요.",
    "그는 노트를 덮었어요.",
    "복도에 발소리만 남았어요.",
    "그는 자리에서 일어났어요.",
    "문이 조용히 닫혔어요.",
]


def _ff(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", *args], capture_output=True, check=True)


def demo_storyboard_payload(n_cuts: int, seconds: int = 4) -> dict:
    """연출 원칙(가드레일)을 통과하는 고정 스토리보드. 컷 수·컷 길이는 인자를 따른다."""
    return {
        "protagonist": {
            "name": "지훈",
            "appearance": (
                "A man in his late twenties, short black hair, slim build, "
                "wearing a loose grey knit sweater and dark trousers."
            ),
        },
        "distortions": [],
        "locations": [
            {
                "name": "회의실",
                "description": (
                    "A small office meeting room with grey carpet, white walls, a long light-wood "
                    "table with eight black chairs, and vertical blinds on the left wall windows."
                ),
            }
        ],
        "cuts": [
            {
                "index": i,
                "image_prompt": (
                    "A wide shot of a quiet office meeting room seen from the far corner. "
                    "Jihoon sits at the end of a long table, looking down at a notebook. "
                    "Pale afternoon light through vertical blinds."
                ),
                "motion_prompt": (
                    "The light slowly moves across the table and his hand stops moving."
                ),
                "narration": _NARRATIONS[(i - 1) % len(_NARRATIONS)],
                "dialogue": [],
                "camera_distance": "wide",
                "duration_seconds": seconds,
                "mood": "평온",
                "location": "회의실",
            }
            for i in range(1, n_cuts + 1)
        ],
    }


class FakeLLM:
    def __init__(self, n_cuts: int) -> None:
        self.payload = demo_storyboard_payload(n_cuts)

    async def complete_json(self, *, system: str, user: str, schema: type[T]):
        await asyncio.sleep(STEP_DELAY_SECONDS)
        raw = json.dumps(self.payload, ensure_ascii=False)
        return schema.model_validate_json(raw), LLMResult(raw_json=raw)


class FakeImage:
    def price_per_image(self, image_size: str) -> Decimal:
        return Decimal(0)

    async def generate(
        self,
        *,
        prompt: str,
        dest: Path,
        references: Sequence[Path] = (),
        aspect_ratio: str = "9:16",
        image_size: str = "1K",
    ) -> ImageResult:
        await asyncio.sleep(STEP_DELAY_SECONDS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        size = "720x1280" if aspect_ratio == "9:16" else "1280x720"
        _ff(["-f", "lavfi", "-i", f"color=c=gray:s={size}", "-frames:v", "1", str(dest)])
        return ImageResult(path=str(dest))


class FakeVideo:
    """제출 즉시 완료되는 것으로 취급한다."""

    def __init__(self) -> None:
        self._durations: dict[int, int] = {}
        self._sizes: dict[int, str] = {}

    def price_per_second(self, resolution: str) -> Decimal:
        return Decimal(0)

    async def submit(
        self,
        *,
        cut_index: int,
        motion_prompt: str,
        first_frame: Path,
        negative_prompt: str,
        aspect_ratio: str,
        resolution: str,
        duration_seconds: int,
        generate_audio: bool = False,
    ) -> VideoHandle:
        self._durations[cut_index] = duration_seconds
        self._sizes[cut_index] = "720x1280" if aspect_ratio == "9:16" else "1280x720"
        return VideoHandle(cut_index=cut_index, operation_name=f"fake/{cut_index}")

    async def poll(self, handle: VideoHandle) -> VideoStatus:
        return VideoStatus(done=True)

    async def fetch(self, handle: VideoHandle, dest: Path) -> VideoResult:
        await asyncio.sleep(STEP_DELAY_SECONDS)
        d = self._durations[handle.cut_index]
        size = self._sizes[handle.cut_index]
        dest.parent.mkdir(parents=True, exist_ok=True)
        _ff([
            "-f", "lavfi", "-i", f"color=c=steelblue:s={size}:d={d}",
            "-f", "lavfi", "-i", f"sine=frequency=200:duration={d}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-shortest", str(dest),
        ])
        return VideoResult(path=str(dest))


class FakeTTS:
    def __init__(self, seconds: float = 3.0) -> None:
        self.seconds = seconds

    async def synthesize(
        self, *, text: str, dest: Path, voice: str, style_prompt: str
    ) -> AudioResult:
        dest.parent.mkdir(parents=True, exist_ok=True)
        rate, n = 24_000, int(24_000 * self.seconds)
        with wave.open(str(dest), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(b"\x00\x00" * n)
        return AudioResult(path=str(dest), duration_s=self.seconds)
