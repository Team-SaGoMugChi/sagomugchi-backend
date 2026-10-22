"""LookProvider의 Gemini 구현 — 컷 그림을 보고 사람 수·성별·크기·카메라 응시를 답한다.

그림 모델은 지시와 다르게 그리는 일이 있다(허리 위 샷인데 사람을 아주 작게, 50대 남자 인물을 여자로).
컷 그림 검사(stages/cut_images.py)가 이 답으로 다시 그릴지 정한다. 그림 한 장에 요청 한 번(약 1원).
"""

from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import types

from ..errors import ProviderError
from .base import SeenFrame, SeenPerson, retry_on_rate_limit
from .gemini_listen import parse_heard

PROMPT = """Look at this image and answer in JSON only.
"people": one entry per clearly visible person (ignore tiny background figures, posters and screens), each with
  "gender": "m" or "f" ("" if you cannot tell),
  "height_ratio": the visible height of that person (from the top of the head to the lowest visible part)
                  divided by the image height, between 0 and 1,
  "legs_visible": true if that person's knees, lower legs or feet are visible in the image.
"looks_at_camera": true if any person looks directly into the camera.
{"people": [{"gender": "m", "height_ratio": 0.6, "legs_visible": false}], "looks_at_camera": false}"""


class GeminiLookProvider:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    async def look(self, *, image: Path) -> SeenFrame:
        async def call():
            return await self._client.aio.models.generate_content(
                model=self._model,
                contents=[types.Part.from_bytes(data=image.read_bytes(), mime_type="image/png"), PROMPT],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
            )

        try:
            data = parse_heard((await retry_on_rate_limit(call, what="그림 확인")).text)
            people = [SeenPerson(gender=str(p.get("gender") or "").lower()[:1],
                                 height_ratio=float(p.get("height_ratio") or 0),
                                 legs_visible=bool(p.get("legs_visible")))
                      for p in data.get("people") or [] if isinstance(p, dict)]
        except Exception as exc:
            raise ProviderError(f"그림 확인 실패 ({self._model}): {exc}") from exc
        return SeenFrame(people=people, looks_at_camera=bool(data.get("looks_at_camera")))
