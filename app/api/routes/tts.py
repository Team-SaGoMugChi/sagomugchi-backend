import base64
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/tts", tags=["tts"])

FISH_URL = "https://api.fish.audio/v1/tts"
CLOVA_URL = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"

# 앱은 말투별 목소리를 CLOVA 이름으로 보낸다(PersonaConfig.voiceForTone). Fish 키가 있으면
# 같은 이름을 Fish 공개 목소리로 바꿔 읽는다 — 앱을 고치지 않고 목소리만 바꿀 수 있다.
# ⚠ 배포 전 교체 필요: 다른 사용자가 올린 목소리라(licensed=false) 상업 이용이 확인되지 않았다.
#    학술제·시연(비상업)용으로만 쓴다. 출시 전에는 동의받은 자체 녹음 목소리 + 유료 플랜으로 바꾼다.
FISH_VOICES: dict[str, str] = {
    "nara": "e1b08ec6597d4770aff6fec0f1908572",  # 친근하고 따뜻한 — "명랑한 어린이"
    "njinho": "448f32968bad4b44b6118ff2c18607d1",  # 차분하고 진중한 — "사색하는 목소리"
    "nminyoung": "d501ce2e2fea44eea189190a2c3480cf",  # 밝고 에너지 넘치는 — "mi 목소리"
    "ndonghyun": "986dfb8e022c4e0bab8d4d41ba50de30",  # 간결하고 솔직한 — "동자승"
}


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    speaker: Literal["nara", "njinho", "nminyoung", "ndonghyun"] = "nara"
    # CLOVA Voice speed: -5 (fastest) to 5 (slowest); 0 keeps the provider default.
    speed: int = Field(default=0, ge=-5, le=5)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value.strip()


def fish_speed(clova_speed: int) -> float:
    """CLOVA 한 칸 = Fish 0.1배. -2(Step1 대화 속도) → 1.2배."""
    return round(1.0 - 0.1 * clova_speed, 2)


async def _fish(settings: Settings, payload: SpeechRequest) -> httpx.Response:
    async with httpx.AsyncClient(timeout=30) as client:
        return await client.post(
            FISH_URL,
            headers={"Authorization": f"Bearer {settings.fish_api_key}", "model": settings.tts_fish_model},
            json={
                "text": payload.text,
                "reference_id": FISH_VOICES[payload.speaker],
                "format": "mp3",
                "language": "ko",
                "prosody": {"speed": fish_speed(payload.speed)},
            },
        )


async def _clova(settings: Settings, payload: SpeechRequest) -> httpx.Response:
    async with httpx.AsyncClient(timeout=30) as client:
        return await client.post(
            CLOVA_URL,
            headers={
                "X-NCP-APIGW-API-KEY-ID": settings.clova_voice_client_id,
                "X-NCP-APIGW-API-KEY": settings.clova_voice_client_secret,
            },
            data={"text": payload.text, "speaker": payload.speaker, "format": "mp3", "speed": str(payload.speed)},
        )


def _audio(response: httpx.Response) -> bytes | None:
    if response.status_code != 200 or not response.content:
        return None
    if not response.headers.get("content-type", "").startswith("audio/"):
        return None
    return response.content


@router.post("")
async def synthesize(payload: SpeechRequest):
    settings = get_settings()
    providers = []
    if settings.fish_api_key:
        providers.append(_fish)
    if settings.clova_voice_client_id and settings.clova_voice_client_secret:
        providers.append(_clova)
    if not providers:
        raise HTTPException(503, "Voice synthesis is not configured")
    # Fish가 실패하면 CLOVA(설정돼 있을 때)로 한 번 더 읽는다. 둘 다 안 되면 앱이 기기 TTS로 읽는다.
    for provider in providers:
        try:
            audio = _audio(await provider(settings, payload))
        except httpx.HTTPError:
            audio = None
        if audio:
            return {"audio_base64": base64.b64encode(audio).decode("ascii"), "mime_type": "audio/mpeg"}
    # Do not expose credentials, user text, or provider response bodies.
    raise HTTPException(502, "Voice synthesis is temporarily unavailable")
