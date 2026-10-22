"""ListenProvider의 Gemini 구현 — 대사 컷 소리를 받아쓰고 목소리 성별을 답한다.

Veo가 만든 대사 목소리를 그대로 쓸지(dialogue_voice="auto") 판단하는 데 쓴다. 짧은 컷 소리 하나에
요청 한 번(수 원 이하)이다.
"""

from __future__ import annotations

import json
from pathlib import Path

from google import genai
from google.genai import types

from ..errors import ProviderError
from .base import HeardSpeech, retry_on_rate_limit

PROMPT = """이 오디오는 짧은 영상 한 장면의 소리다. 사람이 하는 한국어 말을 들리는 그대로 받아써라.
고치거나 다듬지 말고, 웅얼거리거나 덧붙인 말도 들리면 그대로 적는다. 말이 없으면 빈 문자열.
voice는 말하는 목소리가 남자면 "m", 여자면 "f", 말이 없거나 판단할 수 없으면 "".
JSON: {"text": "...", "voice": "m" | "f" | ""}"""


def parse_heard(text: str | None) -> dict:
    """모델이 객체 대신 [객체]로 답하는 일이 있다(관측). 첫 객체를 쓴다."""
    data = json.loads(text or "{}")
    if isinstance(data, list):
        data = next((x for x in data if isinstance(x, dict)), {})
    return data if isinstance(data, dict) else {}


class GeminiListenProvider:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    async def listen(self, *, audio: Path) -> HeardSpeech:
        async def call():
            return await self._client.aio.models.generate_content(
                model=self._model,
                contents=[types.Part.from_bytes(data=audio.read_bytes(), mime_type="audio/wav"), PROMPT],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
            )

        try:
            resp = await retry_on_rate_limit(call, what="대사 듣기")
            data = parse_heard(resp.text)
        except Exception as exc:
            raise ProviderError(f"대사 듣기 실패 ({self._model}): {exc}") from exc
        voice = str(data.get("voice") or "").lower()[:1]
        return HeardSpeech(text=str(data.get("text") or ""), voice=voice if voice in ("m", "f") else "")
