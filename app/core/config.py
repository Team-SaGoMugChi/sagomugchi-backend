from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "Oddo AI Server"
    allowed_origins: list[str] = ["*"]

    # Firestore 쓰기(Firebase Admin SDK)용 서비스 계정 키 경로.
    # Firebase 콘솔 > 프로젝트 설정 > 서비스 계정 > 새 비공개 키 생성 (README.md 참고)
    google_application_credentials: str | None = None

    # Phase 5+에서 사용 (아직 미확정 — ROADMAP.md 참고)
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    # Naver CLOVA Speech(STT). 도메인 하나에 Invoke URL과 Secret Key 두 값이 나오므로
    # 기존 naver_clova_api_key 한 칸으로는 담을 수 없어 둘로 나눴다.
    # Secret Key는 서버에만 둔다 — 앱에 넣으면 APK에서 추출돼 과금 남용이 가능하다.
    clova_speech_invoke_url: str | None = None
    clova_speech_secret: str | None = None
    clova_speech_timeout_sec: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
