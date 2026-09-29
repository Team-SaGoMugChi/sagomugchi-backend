"""Settings로부터 provider 묶음을 조립한다.

스테이지는 이 Providers 객체만 주입받는다. FastAPI에서는 Depends로 넘긴다.
"""

from __future__ import annotations

from dataclasses import dataclass

from google import genai
from openai import AsyncOpenAI

from ..config import Settings
from ..errors import ConfigError
from .base import ImageProvider, LLMProvider, TTSProvider, VideoProvider
from .fake import FakeImage, FakeLLM, FakeTTS, FakeVideo
from .gemini_image import GeminiImageProvider
from .gemini_llm import GeminiLLMProvider
from .gemini_tts import GeminiTTSProvider
from .openai_llm import OpenAILLMProvider
from .veo_video import VeoVideoProvider


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    image: ImageProvider
    video: VideoProvider
    tts: TTSProvider
    # 더미 모드에서는 실제 클라이언트가 없다.
    client: genai.Client | None
    video_client: genai.Client | None


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
    return Providers(
        llm=build_llm(settings, client),
        image=GeminiImageProvider(client, settings.image_model),
        video=VeoVideoProvider(video_client, settings.video_model),
        tts=GeminiTTSProvider(client, settings.tts_model),
        client=client,
        video_client=video_client,
    )


def build_llm(settings: Settings, client: genai.Client) -> LLMProvider:
    """스토리보드 LLM. VIDEOMAKE_LLM_PROVIDER로 Gemini/GPT를 고른다."""
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ConfigError(
                "VIDEOMAKE_LLM_PROVIDER=openai인데 LLM_API_KEY가 없다. "
                ".env에 팀 공용 OpenAI 키를 넣을 것."
            )
        return OpenAILLMProvider(
            AsyncOpenAI(api_key=settings.openai_api_key), settings.openai_model
        )
    return GeminiLLMProvider(client, settings.llm_model)


def build_fake_providers(settings: Settings) -> Providers:
    return Providers(
        llm=FakeLLM(settings.n_cuts),
        image=FakeImage(),
        video=FakeVideo(),
        tts=FakeTTS(),
        client=None,
        video_client=None,
    )
