"""LLMProvider의 OpenAI(GPT) 구현. 구조화 출력(response_format)으로 스키마를 강제한다.

팀 공용 키(`LLM_API_KEY`, 상담 기능과 같은 키)를 쓴다. 스토리보드 단계만 대체하며
이미지·영상·TTS는 여전히 Vertex를 쓴다.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from ..errors import ProviderError
from .base import LLMResult, retry_on_rate_limit

T = TypeVar("T", bound=BaseModel)


class OpenAILLMProvider:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def _sampling(self) -> dict:
        # 추론 모델(gpt-5 계열, o 시리즈)은 temperature를 받지 않는다(넣으면 400).
        if self._model.startswith(("gpt-5", "o1", "o3", "o4")):
            return {}
        return {"temperature": 0.9}  # Gemini 구현과 같은 값

    async def complete_json(
        self, *, system: str, user: str, schema: type[T]
    ) -> tuple[T, LLMResult]:
        started = time.perf_counter()
        try:
            resp = await retry_on_rate_limit(
                lambda: self._client.chat.completions.parse(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format=schema,
                    **self._sampling(),
                ),
                what=f"LLM({self._model})",
            )
        except Exception as exc:
            raise ProviderError(f"LLM 호출 실패 ({self._model}): {exc}") from exc

        elapsed = time.perf_counter() - started
        message = resp.choices[0].message
        if message.refusal:
            raise ProviderError(f"LLM이 응답을 거부했다: {message.refusal}")
        if message.parsed is None:
            raise ProviderError("LLM이 스키마에 맞는 응답을 반환하지 않았다")

        usage = resp.usage
        meta = LLMResult(
            raw_json=message.content or "",
            elapsed_s=elapsed,
            cost_usd=Decimal("0.01"),  # 영상 대비 무시할 수준. 총액 표시용 근사치.
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
        return message.parsed, meta
