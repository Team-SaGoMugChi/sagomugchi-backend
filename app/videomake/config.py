"""설정. 모든 값은 .env 또는 환경변수로 주입된다.

FastAPI 이식 시 이 Settings 객체를 그대로 의존성으로 주입하면 된다.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parent
# 서버 이식 시 프롬프트를 패키지 안으로 옮겼다. 실행 위치와 무관하게 찾는다.
PROMPTS_DIR = PACKAGE_ROOT / "prompts"

# 8초 안에 편안히 읽히는 한국어 나레이션 길이 상한.
NARRATION_MAX_CHARS = 28

# 대사는 Veo가 직접 발화한다. 스파이크에서 8초에 18자 + 12자가 여유 있게 들어갔고
# 말 사이 공백까지 필요하므로 총량을 이 선에서 막는다.
DIALOGUE_MAX_CHARS = 40
DIALOGUE_MAX_LINES = 3

# 대사가 한 줄뿐이면 8초 중 6초가 빈다. Veo는 그 침묵을 지어낸 잡담으로 메운다
# (실제로 관측됨). 주고받는 형태로 시간을 채워 그 여지를 없앤다.
DIALOGUE_MIN_LINES = 2


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="VIDEOMAKE_",
        extra="ignore",
    )

    # 자격증명은 관례상 접두사가 없다.
    # Vertex(Agent Platform)는 ADC로 인증한다. 조직 정책상 API 키는 발급이 막혀 있다.
    # SDK는 os.environ만 읽고 .env는 보지 못하므로, 여기서 받아 Client에 직접 넘긴다.
    google_cloud_project: str = Field(default="", validation_alias="GOOGLE_CLOUD_PROJECT")

    # 리전이 갈린다. 최신 Gemini(3.x LLM/이미지)는 global 엔드포인트에만 있고,
    # Veo는 리전 엔드포인트에만 있다. 그래서 클라이언트를 둘로 띄운다.
    # models.list()는 두 리전 모두에서 거짓 양성을 준다. 실제 호출로만 검증된다.
    google_cloud_location: str = Field(
        default="global", validation_alias="GOOGLE_CLOUD_LOCATION"
    )
    video_location: str = "us-central1"

    # 스토리보드 LLM. 팀 표준은 GPT(openai)이고 키는 상담 기능과 같은 팀 공용
    # LLM_API_KEY를 쓴다. gemini로도 바꿀 수 있다. 이미지·영상·TTS는 어느 쪽이든 Vertex.
    llm_provider: Literal["gemini", "openai"] = "openai"
    openai_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    # gpt-4o-mini는 "영어로 작성"·글자 수 상한을 자주 어겨 3회 안에 통과하지 못했다.
    # gpt-5.5는 가장 적은 재요청으로 통과하고 관찰자 시점 연출도 가장 잘 지켰다(2026-09 비교).
    openai_model: str = "gpt-5.5"

    # --- 모델 문자열 -------------------------------------------------------
    # 자주 바뀐다. 하드코딩하지 않고 `videomake doctor`로 실제 목록과 대조한다.
    llm_model: str = "gemini-3.8-flash"
    image_model: str = "gemini-3.1-flash-image"
    video_model: str = "veo-3.1-fast-generate-preview"
    tts_model: str = "gemini-3.1-flash-tts-preview"
    tts_voice: str = "Charon"

    # --- 렌더 설정 ---------------------------------------------------------
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    video_resolution: Literal["720p", "1080p"] = "720p"
    image_size: Literal["1K", "2K"] = "1K"
    cut_duration_seconds: Literal[4, 6, 8] = 8
    n_cuts: int = 6

    # Veo는 오디오 생성을 끌 수 없다(Developer API에 generate_audio가 없다).
    # 나레이션 명료도를 위해 기본은 완전 mute.
    veo_audio: Literal["mute", "ambient"] = "mute"
    veo_ambient_gain_db: float = -18.0
    fade_seconds: float = 0.4

    # --- 비용 가드 ---------------------------------------------------------
    max_cost_usd: Decimal = Decimal("6.00")

    # --- 실행 ---------------------------------------------------------------
    # true면 Gemini/Veo 대신 ffmpeg로 만든 더미 산출물을 쓴다(providers/fake.py). 과금 0.
    # 기본값이 true다. 실제 생성(작업당 약 $5)은 VIDEOMAKE_DUMMY=false를 명시했을 때만
    # 돈다 — .env에서 이 줄이 빠지거나 오래된 .env를 써도 과금되지 않게 하기 위함.
    dummy: bool = True
    # 생성물(이미지·영상)은 커밋하지 않는다. .cache/는 이미 .gitignore에 있다.
    jobs_dir: Path = Path(".cache/videomake/jobs")
    poll_interval_seconds: float = 10.0
    poll_timeout_seconds: float = 900.0
    video_concurrency: int = 2
    # Vertex 무료 체험 프로젝트의 이미지 할당량은 매우 빡빡하다. 병렬로 쏘면
    # 전부 429로 되돌아온다. 직렬이 결과적으로 더 빠르다.
    image_concurrency: int = 1

    # .env의 값은 전부 문자열로 들어온다. Literal[int]는 자동 변환되지 않으므로
    # 검증 전에 정수로 바꿔준다.
    @field_validator("cut_duration_seconds", "n_cuts", mode="before")
    @classmethod
    def _coerce_int(cls, v: object) -> object:
        return int(v) if isinstance(v, str) and v.strip() else v

    @property
    def prompts_dir(self) -> Path:
        return PROMPTS_DIR


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
