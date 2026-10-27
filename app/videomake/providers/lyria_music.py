"""MusicProvider의 Vertex Lyria 2 구현.

Lyria는 google-genai SDK에 없어서 Vertex REST(predict)를 직접 부른다. 인증은 다른 Vertex 호출과
같은 gcloud ADC다. 한 번에 48kHz 스테레오 WAV 약 32초를 돌려준다(보컬 없음).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import random
import time
from pathlib import Path

import google.auth
import google.auth.transport.requests
import httpx

from ..cost import MUSIC_PRICE_PER_CLIP
from ..errors import ProviderError
from ..models import AudioResult

log = logging.getLogger(__name__)

# 드럼·비트가 들어가면 쇼츠 배경음악이 싸 보인다(2026-10 사용자 평가). 영화 배경음악 쪽으로 둔다.
NEGATIVE = (
    "vocals, singing, lyrics, drums, beat, hip hop, lo-fi, EDM, cheesy, upbeat corporate, "
    "ukulele, whistling, dramatic climax, loud"
)


class LyriaMusicProvider:
    def __init__(self, *, project: str, model: str = "lyria-002", location: str = "us-central1",
                 max_retries: int = 4) -> None:
        self._url = (
            f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/"
            f"{location}/publishers/google/models/{model}:predict"
        )
        self._max_retries = max_retries
        self._creds = None

    def _token(self) -> str:
        if self._creds is None:
            self._creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not self._creds.valid:
            self._creds.refresh(google.auth.transport.requests.Request())
        return self._creds.token

    async def generate(self, *, prompt: str, dest: Path) -> AudioResult:
        started = time.perf_counter()
        body = {"instances": [{"prompt": prompt, "negative_prompt": NEGATIVE}], "parameters": {"sample_count": 1}}
        last = ""
        async with httpx.AsyncClient(timeout=180) as client:
            for attempt in range(1, self._max_retries + 1):
                token = await asyncio.to_thread(self._token)
                resp = await client.post(self._url, json=body, headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 200:
                    preds = resp.json().get("predictions") or []
                    if preds and preds[0].get("bytesBase64Encoded"):
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(base64.b64decode(preds[0]["bytesBase64Encoded"]))
                        return AudioResult(path=str(dest), cost_usd=MUSIC_PRICE_PER_CLIP,
                                           elapsed_s=time.perf_counter() - started)
                    last = "빈 응답(안전 필터일 수 있음)"
                    break
                last = f"{resp.status_code} {resp.text[:200]}"
                if resp.status_code not in (429, 500, 503):
                    break
                if attempt < self._max_retries:
                    await asyncio.sleep(min(2**attempt, 30) + random.uniform(0, 2))
        raise ProviderError(f"배경음악 생성 실패: {last}")
