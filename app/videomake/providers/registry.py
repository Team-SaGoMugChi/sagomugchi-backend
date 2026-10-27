"""Settings로부터 provider 묶음을 조립한다.

스테이지는 이 Providers 객체만 주입받는다. FastAPI에서는 Depends로 넘긴다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from google import genai
from openai import AsyncOpenAI

from ..config import Settings
from ..errors import ConfigError
from .base import (
    ImageProvider,
    ListenProvider,
    LLMProvider,
    LookProvider,
    TTSProvider,
    VideoProvider,
)
from .fake import FakeImage, FakeListen, FakeLLM, FakeTTS, FakeVideo
from .gemini_image import GeminiImageProvider
from .gemini_listen import GeminiListenProvider
from .gemini_look import GeminiLookProvider
from .gemini_llm import GeminiLLMProvider
from .gemini_tts import GeminiTTSProvider
from .openai_llm import OpenAILLMProvider
from .veo_video import VeoVideoProvider

log = logging.getLogger(__name__)


def build_video(settings: Settings, video_client: genai.Client, job_key: str = "job") -> VideoProvider:
    """영상 provider. evolink면 그림 업로드 주소와 함께 만들고, 대사 컷만 Veo로 보낼 수도 있다."""
    veo = VeoVideoProvider(video_client, settings.video_model)
    if settings.video_provider != "evolink":
        return veo
    from .evolink_video import EvolinkVideoProvider
    from .image_host import FirebaseImageHost
    from .routing_video import RoutingVideoProvider

    if not settings.evolink_api_key:
        raise ConfigError("VIDEOMAKE_VIDEO_PROVIDER=evolink인데 VIDEOMAKE_EVOLINK_API_KEY가 없다.")
    host = FirebaseImageHost(settings.upload_bucket, settings.upload_credentials)
    evolink = EvolinkVideoProvider(
        api_key=settings.evolink_api_key,
        model=settings.evolink_video_model,
        image_host=host,
        base_url=settings.evolink_base_url,
        job_key=job_key,
        quality=settings.evolink_quality or None,
    )
    if settings.dialogue_video_provider == "veo":
        return RoutingVideoProvider(default=evolink, speaking=veo)
    return evolink


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    image: ImageProvider
    video: VideoProvider
    tts: TTSProvider
    # 더미 모드에서는 실제 클라이언트가 없다.
    client: genai.Client | None
    video_client: genai.Client | None
    # 대사 컷 소리 듣기(dialogue_voice="auto"). 없으면 대사는 TTS로 더빙한다.
    listen: ListenProvider | None = None
    # 컷 그림 검사. 없으면 검사하지 않는다(더미 모드).
    look: LookProvider | None = None
    # 나레이션 전용 목소리(Fish 등). 없으면 tts로 읽는다.
    narration_tts: TTSProvider | None = None


def build_providers(settings: Settings) -> Providers:
    if settings.dummy:
        return build_fake_providers(settings)
    if not settings.google_cloud_project:
        raise ConfigError(
            "GOOGLE_CLOUD_PROJECT가 없다. .env.example을 .env로 복사하고 "
            "프로젝트 ID를 넣을 것. 인증은 `gcloud auth application-default login`."
        )
    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )
    video_client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.video_location,
    )
    gemini_tts = GeminiTTSProvider(client, settings.tts_model)
    return Providers(
        llm=build_llm(settings, client),
        image=GeminiImageProvider(client, settings.image_model),
        video=build_video(settings, video_client),
        tts=gemini_tts,
        client=client,
        video_client=video_client,
        listen=GeminiListenProvider(client, settings.listen_model),
        look=GeminiLookProvider(client, settings.listen_model),
        narration_tts=build_narration_tts(settings, gemini_tts),
    )


def build_narration_tts(settings: Settings, gemini_tts: TTSProvider) -> TTSProvider | None:
    """나레이션 목소리. Fish 키가 없으면(팀원 로컬 등) 기존 Gemini 목소리로 읽는다."""
    if settings.narration_tts != "fish":
        return None
    if not settings.fish_api_key:
        log.warning("VIDEOMAKE_NARRATION_TTS=fish인데 FISH_API_KEY가 없다 — 나레이션은 Gemini로 읽는다.")
        return None
    from .fish_tts import FallbackTTS, FishTTSProvider

    fish = FishTTSProvider(
        api_key=settings.fish_api_key,
        model=settings.fish_model,
        voice_id=settings.fish_voice_id,
        speed=settings.fish_speed,
    )
    return FallbackTTS(fish, gemini_tts)


def build_llm(settings: Settings, client: genai.Client) -> LLMProvider:
    """스토리보드 LLM. VIDEOMAKE_LLM_PROVIDER로 Gemini/GPT를 고른다."""
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ConfigError(
                "VIDEOMAKE_LLM_PROVIDER=openai인데 VIDEOMAKE_OPENAI_API_KEY가 없다. "
                ".env에 영상용 OpenAI 키를 넣을 것(상담용 LLM_API_KEY와 별개)."
            )
        return OpenAILLMProvider(
            AsyncOpenAI(api_key=settings.openai_api_key), settings.openai_model
        )
    return GeminiLLMProvider(client, settings.llm_model)


def build_fake_providers(settings: Settings) -> Providers:
    return Providers(
        # 더미는 허용 범위의 가장 짧은 영상(최소 컷 수 × 4초)을 만든다.
        llm=FakeLLM(settings.min_cuts),
        image=FakeImage(),
        video=FakeVideo(),
        tts=FakeTTS(),
        client=None,
        video_client=None,
        listen=FakeListen(),
    )
