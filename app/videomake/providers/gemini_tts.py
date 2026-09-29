"""TTSProvider의 Gemini 구현.

Gemini TTS는 WAV 헤더 없는 raw PCM(24kHz / 16bit / mono)을 반환한다.
ffmpeg에 넣기 전에 헤더를 씌워야 한다.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import wave
from decimal import Decimal
from pathlib import Path

from google import genai
from google.genai import types

from ..cost import TTS_PRICE_PER_CUT
from ..errors import ProviderError
from ..models import AudioResult

log = logging.getLogger(__name__)

SAMPLE_RATE = 24_000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1


class GeminiTTSProvider:
    def __init__(
        self, client: genai.Client, model: str, max_retries: int = 4
    ) -> None:
        self._client = client
        self._model = model
        self._max_retries = max_retries

    async def synthesize(
        self, *, text: str, dest: Path, voice: str, style_prompt: str
    ) -> AudioResult:
        started = time.perf_counter()
        # 오디오가 비어 오는 일시적 실패가 관측된다. 같은 요청이 재시도하면 통과한다.
        pcm: bytes | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                pcm = await self._call(style_prompt, voice)
            except Exception as exc:
                if attempt == self._max_retries:
                    raise ProviderError(f"TTS 실패 ({self._model}): {exc}") from exc
                pcm = None
            if pcm:
                break
            if attempt < self._max_retries:
                delay = min(2**attempt, 20) + random.uniform(0, 1)
                log.warning(
                    "TTS 재시도 %d/%d (%.1fs 후): %.20s…",
                    attempt, self._max_retries, delay, text,
                )
                await asyncio.sleep(delay)

        if not pcm:
            raise ProviderError(
                f"TTS가 {self._max_retries}회 모두 오디오를 반환하지 않았다: {text[:20]!r}"
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dest), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)

        duration = len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
        return AudioResult(
            path=str(dest),
            duration_s=duration,
            cost_usd=Decimal(TTS_PRICE_PER_CUT),
            elapsed_s=time.perf_counter() - started,
        )

    async def _call(self, style_prompt: str, voice: str) -> bytes | None:
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=style_prompt,
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    language_code="ko-KR",
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    ),
                ),
            ),
        )
        return _first_audio_blob(resp)


def _first_audio_blob(resp: types.GenerateContentResponse) -> bytes | None:
    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            data = getattr(part, "inline_data", None)
            if data is not None and data.data:
                return data.data
    return None
