"""LLMProvider의 Gemini 구현. 구조화 출력(response_schema)을 강제한다."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from ..errors import ProviderError
from .base import LLMResult, retry_on_rate_limit

T = TypeVar("T", bound=BaseModel)


class GeminiLLMProvider:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    async def complete_json(
        self, *, system: str, user: str, schema: type[T]
    ) -> tuple[T, LLMResult]:
        started = time.perf_counter()
        try:
            resp = await retry_on_rate_limit(
                lambda: self._client.aio.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.9,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                ),
                what=f"LLM({self._model})",
            )
        except Exception as exc:
            raise ProviderError(f"LLM 호출 실패 ({self._model}): {exc}") from exc

        elapsed = time.perf_counter() - started
        text = resp.text or ""
        if not text.strip():
            raise ProviderError("LLM이 빈 응답을 반환했다")

        usage = resp.usage_metadata
        meta = LLMResult(
            raw_json=text,
            elapsed_s=elapsed,
            cost_usd=Decimal("0.01"),  # 영상 대비 무시할 수준. 총액 표시용 근사치.
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )
        return schema.model_validate_json(text), meta
