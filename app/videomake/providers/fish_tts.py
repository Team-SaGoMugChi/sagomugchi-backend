"""TTSProvider의 Fish Audio 구현 — 나레이션용.

Fish Audio는 사람들이 올린 목소리를 reference_id로 골라 읽힌다. 한국어 쇼츠 말투 목소리가 많다.
연기 지시(style_prompt)와 Gemini 목소리 이름(voice)은 쓰지 않는다 — 목소리 자체가 말투를 갖고 있다.

응답은 스트리밍 WAV라 헤더의 길이 칸이 비어 있다(길이를 읽으면 수만 초로 나온다).
ffmpeg로 24kHz 모노 WAV로 다시 저장해 다른 TTS 결과와 같은 규격으로 맞춘다.
"""

from __future__ import annotations

import asyncio
import logging
import random
import shutil
import subprocess
import time
import wave
from pathlib import Path

import httpx

from ..cost import fish_price
from ..errors import ProviderError
from ..models import AudioResult

log = logging.getLogger(__name__)

URL = "https://api.fish.audio/v1/tts"
# 쇼츠 목소리는 한 글자에 약 0.13초. 이보다 훨씬 길면 대본에 없는 말을 덧붙인 것이다.
SECONDS_PER_CHAR_MAX = 0.2
SECONDS_SLACK = 0.6
TAKES = 3


def max_plausible_seconds(text: str) -> float:
    return SECONDS_SLACK + SECONDS_PER_CHAR_MAX * len(text)


class FishTTSProvider:
    def __init__(
        self, *, api_key: str, model: str, voice_id: str, speed: float = 1.0, max_retries: int = 4
    ) -> None:
        self._key = api_key
        self._model = model
        self._voice_id = voice_id
        self._speed = speed
        self._max_retries = max_retries

    async def synthesize(
        self, *, text: str, dest: Path, voice: str, style_prompt: str
    ) -> AudioResult:
        started = time.perf_counter()
        dest.parent.mkdir(parents=True, exist_ok=True)
        limit = max_plausible_seconds(text)
        for attempt in range(1, TAKES + 1):
            raw = await self._call(text)
            tmp = dest.with_suffix(".fish.wav")
            tmp.write_bytes(raw)
            try:
                _to_wav(tmp, dest)
            finally:
                tmp.unlink(missing_ok=True)
            with wave.open(str(dest)) as wf:
                duration = wf.getnframes() / wf.getframerate()
            if duration <= limit:
                break
            # 가끔 문장을 다 읽고도 멈추지 않고 없는 말을 붙인다(2026-10, 10번 중 1번꼴 관측).
            log.warning("Fish 나레이션이 %.1fs로 너무 길다(상한 %.1fs) — 다시 읽힌다 %d/%d: %s",
                        duration, limit, attempt, TAKES, text)
        else:
            dest.unlink(missing_ok=True)
            raise ProviderError(f"Fish 나레이션이 {TAKES}번 모두 대본보다 길게 읽혔다: {text}")
        return AudioResult(
            path=str(dest),
            duration_s=duration,
            cost_usd=fish_price(self._model, len(text.encode("utf-8"))),
            elapsed_s=time.perf_counter() - started,
        )

    async def _call(self, text: str) -> bytes:
        body = {
            "text": text,
            "reference_id": self._voice_id,
            "format": "wav",
            "language": "ko",
            "prosody": {"speed": self._speed},
        }
        headers = {"Authorization": f"Bearer {self._key}", "model": self._model}
        last = ""
        async with httpx.AsyncClient(timeout=120) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    resp = await client.post(URL, json=body, headers=headers)
                    if resp.status_code == 200 and resp.content[:4] == b"RIFF":
                        return resp.content
                    last = f"{resp.status_code} {resp.text[:200]}"
                    # 키·요청 오류는 다시 보내도 같다. 한도(429)와 서버 오류만 다시 시도한다.
                    if resp.status_code not in (429, 500, 502, 503, 504):
                        break
                except httpx.HTTPError as exc:
                    last = str(exc)
                if attempt < self._max_retries:
                    delay = min(2**attempt, 20) + random.uniform(0, 1)
                    log.warning("Fish TTS 재시도 %d/%d (%.1fs 후): %s", attempt, self._max_retries, delay, last)
                    await asyncio.sleep(delay)
        raise ProviderError(f"Fish TTS 실패 ({self._model}): {last}")


class FallbackTTS:
    """앞 provider가 실패하면 뒤 provider로 읽는다. 나레이션이 비면 영상이 완성되지 않기 때문이다."""

    def __init__(self, primary, fallback) -> None:
        self._primary = primary
        self._fallback = fallback

    async def synthesize(
        self, *, text: str, dest: Path, voice: str, style_prompt: str
    ) -> AudioResult:
        try:
            return await self._primary.synthesize(text=text, dest=dest, voice=voice, style_prompt=style_prompt)
        except Exception as exc:
            log.warning("나레이션 기본 목소리 실패 — 예비 목소리로 읽는다: %s", exc)
            return await self._fallback.synthesize(text=text, dest=dest, voice=voice, style_prompt=style_prompt)


def _to_wav(src: Path, dest: Path) -> None:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise ProviderError("ffmpeg를 찾을 수 없다.")
    proc = subprocess.run(
        [exe, "-loglevel", "error", "-y", "-i", str(src), "-ar", "24000", "-ac", "1", str(dest)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise ProviderError(f"Fish 오디오 변환 실패: {proc.stderr[-300:]}")

