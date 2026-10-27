"""설정. 모든 값은 .env 또는 환경변수로 주입된다.

FastAPI 이식 시 이 Settings 객체를 그대로 의존성으로 주입하면 된다.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parent
# 서버 이식 시 프롬프트를 패키지 안으로 옮겼다. 실행 위치와 무관하게 찾는다.
PROMPTS_DIR = PACKAGE_ROOT / "prompts"

# Veo가 만들 수 있는 컷 길이(초). 컷마다 LLM이 이 중에서 고른다.
CUT_DURATIONS = (4, 6, 8)
CutSeconds = Literal[4, 6, 8]

# 나레이션 낭독 속도(초당 글자 수, 공백 포함). "보통 대화 속도" 낭독 지시로 목소리 6종을
# 재보니 초당 5.0~6.1자였다(2026-10). 가장 느린 값을 써서 어떤 목소리도 컷 안에 끝나게 한다.
NARRATION_CHARS_PER_SECOND = 5
# 컷 시작 뒤 목소리가 들어오기까지(settings.narration_delay_ms)와 끝에 숨 쉴 틈을 남긴다.
NARRATION_MARGIN_SECONDS = 0.8

# 컷과 컷 사이를 겹쳐 넘기는 시간(초). 짧은 컷이 툭툭 끊겨 보이지 않게 한다.
# 컷이 겹치는 만큼 영상 전체가 짧아지므로 나레이션 글자 수 계산에도 들어간다.
CROSSFADE_SECONDS = 0.3

# 나레이션도 대사도 없는 컷(화면만 보여주는 컷)은 이 길이만 쓴다. 릴스처럼 짧게 넘어간다.
SILENT_CUT_SECONDS = 4
# 무음 컷이 이보다 많이 이어지면 이야기가 끊긴다.
MAX_SILENT_RUN = 2

# 대사 컷은 한 사람이 한 줄만 말하고, 화면에는 그 사람만 보인다(숏–리버스숏).
# 화면에 두 사람이 있으면 Veo가 대사를 엉뚱한 사람 입에 붙였다(6번 중 5번 관측).
# 주고받는 말은 컷을 나눠 번갈아 보여준다. 남는 시간에 Veo가 덧붙인 말소리는
# 대사 더빙(stages/dialogue_voice.py)이 줄여서 들리지 않는다.
DIALOGUE_MIN_LINES = 1
DIALOGUE_MAX_LINES = 1
DIALOGUE_MIN_SECONDS = 4
# 대사는 컷 시작 후 약 1초 조용하다가 시작한다. 대화 속도는 초당 약 6자.
DIALOGUE_CHARS_PER_SECOND = 6
DIALOGUE_LEAD_SECONDS = 1.0


def narration_chars_for_window(window: float) -> int:
    """나레이션이 읽힐 수 있는 시간(초)에 들어가는 글자 수."""
    return max(0, int(NARRATION_CHARS_PER_SECOND * (window - NARRATION_MARGIN_SECONDS)))


def narration_max_chars(seconds: int) -> int:
    """무음 컷이 뒤따르지 않는 컷 하나의 나레이션 글자 수 상한(4초 14자, 6초 24자, 8초 34자).
    다음 컷과 겹치는 시간(크로스페이드)만큼 빠진다."""
    return narration_chars_for_window(seconds - CROSSFADE_SECONDS)


def dialogue_max_chars(seconds: int) -> int:
    """컷 길이(초)에 맞는 대사 글자 수 상한(4초 14자, 6초 26자, 8초 38자).
    말 시작 전 조용한 시간과 다음 컷과 겹치는 시간·여유를 뺀다."""
    speak = seconds - CROSSFADE_SECONDS - DIALOGUE_LEAD_SECONDS - CROSSFADE_SECONDS
    return max(0, int(DIALOGUE_CHARS_PER_SECOND * speak))


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

    # 스토리보드 LLM. 팀 표준은 GPT(openai)다. gemini로도 바꿀 수 있다.
    # 이미지·영상·TTS는 어느 쪽이든 Vertex.
    llm_provider: Literal["gemini", "openai"] = "openai"
    # 스토리보드를 한 번의 호출로(single, 기본) 만들지, 작가·감독·스크립터로 나눈 제작팀으로(team) 만들지.
    planner: Literal["single", "team"] = "single"
    # 제작팀 모드의 촬영감독 단계: 나레이션·무음 컷 일부를 한 번 생성 안에서 2~3개 샷으로 나눈다.
    shot_split: bool = True
    # 영상 전용 OpenAI 키(VIDEOMAKE_OPENAI_API_KEY). 팀 결정으로 키를 용도별로 나눈다 —
    # 상담의 LLM_API_KEY는 읽지 않는다. 사용량·비용을 기능별로 따로 보기 위함.
    openai_api_key: str = ""
    # gpt-4o-mini는 "영어로 작성"·글자 수 상한을 자주 어겨 3회 안에 통과하지 못했다.
    # gpt-5.5는 가장 적은 재요청으로 통과하고 관찰자 시점 연출도 가장 잘 지켰다(2026-09 비교).
    openai_model: str = "gpt-5.5"

    # --- 모델 문자열 -------------------------------------------------------
    # 자주 바뀐다. 하드코딩하지 않고 `videomake doctor`로 실제 목록과 대조한다.
    llm_model: str = "gemini-3.8-flash"
    image_model: str = "gemini-3.1-flash-image"
    video_model: str = "veo-3.1-fast-generate-preview"
    tts_model: str = "gemini-3.1-flash-tts-preview"
    # Gemini 나레이션 목소리(Fish를 못 쓸 때). 2026-10 스타일 9종 비교에서 Autonoe(일상 브이로그 말투)로 정했다.
    # 이전 Leda는 느리고 우울하게 들린다는 평가였다.
    tts_voice: str = "Autonoe"

    # --- 렌더 설정 ---------------------------------------------------------
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    video_resolution: Literal["720p", "1080p"] = "720p"
    image_size: Literal["1K", "2K"] = "1K"
    # 영상 길이는 일기마다 LLM이 정한다(컷 수·컷별 길이). 그 범위만 여기서 막는다.
    # 짧은 일기에 48초를 고정으로 만들면 생성 시간과 비용이 낭비된다.
    min_cuts: int = 3
    max_cuts: int = 10
    min_total_seconds: int = 12
    max_total_seconds: int = 40

    # 대사 없는 컷의 장면 소리(발소리·거리·그릇 소리). "ambient"(기본)는 Veo가 모든 컷에서
    # 장면 소리를 만들고 나레이션 아래에 작게 깐다 — 무음 컷이 완전히 비지 않는다.
    # Veo 3.1 Fast 720p 공개 단가는 소리 포함 초당 $0.10(cost.py와 같다). "mute"는 소리를 만들지 않는다.
    veo_audio: Literal["mute", "ambient"] = "ambient"
    # 대사 컷 목소리. "auto"(기본)는 Veo가 만든 목소리를 들어 보고(listen_model) 대본대로 말했고
    # 인물 성별과 맞으면 그대로 쓰고, 말을 덧붙였거나 틀렸거나 성별이 다르면 그 컷만 TTS로 더빙한다.
    # Veo 목소리는 입 모양과 훨씬 잘 맞는다(립싱크 LSE-C 원래 목소리 2.2~3.5 vs TTS 1.5~2.2, 2026-10 측정).
    # "tts"는 모든 대사 컷을 인물별 TTS로, "veo"는 확인 없이 Veo 목소리 그대로.
    dialogue_voice: Literal["auto", "tts", "veo"] = "auto"
    # 영상 provider. "veo"(기본)는 Google Vertex Veo. "evolink"는 evolink.ai로 다른 회사 모델을
    # 부른다(providers/evolink_video.py의 MODELS — Grok Imagine 등). dialogue_video_provider="veo"면
    # 대사 컷만 Veo로 보낸다(입 모양이 맞는 모델 + 싼 모델 섞어 쓰기).
    video_provider: Literal["veo", "evolink"] = "veo"
    dialogue_video_provider: Literal["same", "veo"] = "same"
    evolink_api_key: str = ""
    evolink_base_url: str = "https://api.evolink.ai"
    evolink_video_model: str = "grok-imagine-image-to-video-beta"
    # 비우면 모델 기본 해상도(MODELS의 quality). 값이 있으면 그 해상도로 요청한다(예: 480p — 싸다).
    evolink_quality: str = ""
    # evolink는 그림을 URL로 받는다. 컷 그림을 올릴 Firebase Storage 버킷과 서비스 계정 키.
    upload_bucket: str = "oddo-emotion-diary.firebasestorage.app"
    upload_credentials: str = Field(
        default="", validation_alias=AliasChoices("VIDEOMAKE_UPLOAD_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS")
    )
    listen_model: str = "gemini-2.5-flash"  # 대사 소리 듣기·컷 그림 확인
    # 컷 그림 검사: 사람 수·성별·허리 위 샷 크기·카메라 응시가 틀리면 다시 그린다(최대 횟수).
    image_check_retries: int = 2
    # 장면 소리 크기(dBFS RMS). Veo가 만든 장면 소리는 컷마다 -45~-15dB로 들쭉날쭉해서
    # 고정 이득 대신 이 크기로 맞춘다. 나레이션(약 -13dB) 아래에서는 더 작게.
    veo_ambient_gain_db: float = -36.0  # 나레이션 아래
    veo_ambient_solo_gain_db: float = -28.0  # 목소리 없는 컷
    fade_seconds: float = 0.4

    # --- 나레이션 목소리 ----------------------------------------------------
    # "fish"(기본)는 Fish Audio의 한국어 쇼츠 목소리로 읽는다 — 사람들이 실제로 쓰는 말투라
    # Gemini보다 덜 딱딱하고 약 30% 빠르다(2026-10 비교). 키가 없거나 실패하면 Gemini(tts_voice)로 읽는다.
    # 대사 더빙은 인물별 목소리가 필요해서 계속 Gemini TTS를 쓴다.
    narration_tts: Literal["fish", "gemini"] = "fish"
    fish_api_key: str = Field(default="", validation_alias=AliasChoices("FISH_API_KEY", "VIDEOMAKE_FISH_API_KEY"))
    # s2.1-pro-free는 무료(2026-11-30까지 안내, 보장 없음). 유료는 s2.1-pro($15 / 100만 바이트, 한 편 약 1센트).
    fish_model: str = "s2.1-pro-free"
    # Fish 공개 목소리 "20대 여자_나긋나긋 쇼츠"(한국어 사용 6만 회, 2026-10). 연예인 복제 목소리는 쓰지 않는다.
    fish_voice_id: str = "4e118bfbb83e401c84699c09b5f08257"
    fish_speed: float = 1.0

    # --- 편집 ---------------------------------------------------------------
    # 목소리가 끝난 뒤 남는 정적을 잘라 컷을 줄인다(쇼츠 편집 관행: 0.3~0.5초 넘는 공백은 자른다).
    # 무음 컷(화면만 보여주는 동작)과 편집 계획이 "끝까지 보여줄 동작"으로 고른 컷은 자르지 않는다.
    tight_edit: bool = True
    # 목소리가 끝난 뒤 남기는 여유. 0.35초는 다급하게 느껴졌고 1.1초로 정했다(2026-10 사용자 비교).
    edit_tail_seconds: float = 1.1
    edit_min_cut_seconds: float = 2.2
    narration_delay_ms: int = 300  # 컷이 시작하고 목소리가 들어오기까지

    # --- 배경음악 ------------------------------------------------------------
    # 편집 계획(LLM)이 분위기상 필요하다고 본 구간에만 깐다. 대부분의 영상은 음악 없이
    # 목소리와 장면 소리만 둔다. 깔 때는 목소리 아래에서 작게 들리게 한다.
    music: bool = True
    music_model: str = "lyria-002"
    music_level_db: float = -34.0  # 음악 크기(dBFS RMS). 나레이션은 약 -15dB

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
    @field_validator(
        "min_cuts", "max_cuts", "min_total_seconds", "max_total_seconds", mode="before"
    )
    @classmethod
    def _coerce_int(cls, v: object) -> object:
        return int(v) if isinstance(v, str) and v.strip() else v

    @property
    def prompts_dir(self) -> Path:
        return PROMPTS_DIR


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
