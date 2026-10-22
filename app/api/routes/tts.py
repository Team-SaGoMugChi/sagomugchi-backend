import base64
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

router = APIRouter(prefix="/tts", tags=["tts"])


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    speaker: Literal["nara", "njinho", "nminyoung", "ndonghyun"] = "nara"

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value.strip()


@router.post("")
async def synthesize(payload: SpeechRequest):
    settings = get_settings()
    if not settings.clova_voice_client_id or not settings.clova_voice_client_secret:
        raise HTTPException(503, "Voice synthesis is not configured")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts",
                headers={
                    "X-NCP-APIGW-API-KEY-ID": settings.clova_voice_client_id,
                    "X-NCP-APIGW-API-KEY": settings.clova_voice_client_secret,
                },
                data={"text": payload.text, "speaker": payload.speaker, "format": "mp3", "speed": "0"},
            )
            response.raise_for_status()
    except httpx.HTTPError:
        # Do not expose credentials, user text, or provider response bodies.
        raise HTTPException(502, "Voice synthesis is temporarily unavailable") from None
    if not response.content or not response.headers.get("content-type", "").startswith("audio/"):
        raise HTTPException(502, "Invalid voice synthesis response")
    return {"audio_base64": base64.b64encode(response.content).decode("ascii"), "mime_type": "audio/mpeg"}
