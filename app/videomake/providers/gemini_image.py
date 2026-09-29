"""ImageProvider의 Gemini(nano banana) 구현.

레퍼런스 이미지는 별도 파라미터가 아니라 contents에 이미지 파트로 넣는다.
캐릭터 시트를 앞에 붙이고 그 뒤에 컷 프롬프트를 두면 캐릭터가 유지된다.
"""

from __future__ import annotations

import mimetypes
import time
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from google import genai
from google.genai import types

from ..cost import image_price_per_image
from ..errors import ProviderError
from ..models import ImageResult
from .base import retry_on_rate_limit


class GeminiImageProvider:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    def price_per_image(self, image_size: str) -> Decimal:
        return image_price_per_image(self._model, image_size)

    async def generate(
        self,
        *,
        prompt: str,
        dest: Path,
        references: Sequence[Path] = (),
        aspect_ratio: str = "9:16",
        image_size: str = "1K",
    ) -> ImageResult:
        parts: list[types.Part] = []
        for ref in references:
            mime = mimetypes.guess_type(ref.name)[0] or "image/png"
            parts.append(
                types.Part.from_bytes(data=ref.read_bytes(), mime_type=mime)
            )
        parts.append(types.Part.from_text(text=prompt))

        started = time.perf_counter()
        try:
            resp = await retry_on_rate_limit(
                lambda: self._client.aio.models.generate_content(
                    model=self._model,
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio=aspect_ratio,
                            image_size=image_size,
                        ),
                    ),
                ),
                what=f"이미지({self._model})",
                # 할당량이 분 단위로 리셋된다. 한 번의 창을 넘길 만큼은 기다린다.
                max_retries=8,
            )
        except Exception as exc:
            raise ProviderError(f"이미지 생성 실패 ({self._model}): {exc}") from exc

        elapsed = time.perf_counter() - started
        blob = _first_image_blob(resp)
        if blob is None:
            raise ProviderError(
                "응답에 이미지가 없다. 안전 필터에 걸렸을 가능성이 있다: "
                f"{_finish_reason(resp)}"
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        return ImageResult(
            path=str(dest),
            cost_usd=self.price_per_image(image_size),
            elapsed_s=elapsed,
        )


def _first_image_blob(resp: types.GenerateContentResponse) -> bytes | None:
    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            data = getattr(part, "inline_data", None)
            if data is not None and data.data:
                return data.data
    return None


def _finish_reason(resp: types.GenerateContentResponse) -> str:
    reasons = [str(c.finish_reason) for c in (resp.candidates or [])]
    return ", ".join(reasons) or "unknown"
