"""Provider 인터페이스.

모든 외부 생성 모델은 이 뒤에 둔다. Veo는 VideoProvider의 한 구현체일 뿐이고
교체 가능해야 한다. 스테이지 코드는 구체 구현을 절대 import 하지 않는다.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from ..models import AudioResult, ImageResult, VideoHandle, VideoResult, VideoStatus

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


def is_rate_limited(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


async def retry_on_rate_limit(
    call: Callable[[], Awaitable[R]], *, what: str, max_retries: int = 5
) -> R:
    """Vertex의 공유 용량 429는 흔하고 대개 일시적이다. 지수 백오프로 넘긴다."""
    for attempt in range(1, max_retries + 1):
        try:
            return await call()
        except Exception as exc:
            if not is_rate_limited(exc) or attempt == max_retries:
                raise
            delay = min(2**attempt, 30) + random.uniform(0, 2)
            log.warning(
                "%s rate limit. %.1fs 후 재시도 (%d/%d)",
                what, delay, attempt, max_retries,
            )
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


class LLMResult(BaseModel):
    """구조화 출력 + 부가 정보."""

    raw_json: str
    elapsed_s: float = 0.0
    cost_usd: Decimal = Decimal(0)
    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class LLMProvider(Protocol):
    async def complete_json(
        self, *, system: str, user: str, schema: type[T]
    ) -> tuple[T, LLMResult]: ...


@runtime_checkable
class ImageProvider(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        dest: Path,
        references: Sequence[Path] = (),
        aspect_ratio: str = "9:16",
        image_size: str = "1K",
    ) -> ImageResult: ...

    def price_per_image(self, image_size: str) -> Decimal: ...


@runtime_checkable
class VideoProvider(Protocol):
    """submit / poll / fetch를 분리한다.

    컷 6개를 한 번에 제출하고 한 루프에서 모아 폴링하기 위함이고,
    FastAPI에서는 submit 후 핸들을 DB에 저장하고 워커가 poll하는 구조로
    그대로 확장된다.
    """

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
    ) -> VideoHandle: ...

    async def poll(self, handle: VideoHandle) -> VideoStatus: ...

    async def fetch(self, handle: VideoHandle, dest: Path) -> VideoResult: ...

    def price_per_second(self, resolution: str) -> Decimal: ...


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(
        self, *, text: str, dest: Path, voice: str, style_prompt: str
    ) -> AudioResult: ...
