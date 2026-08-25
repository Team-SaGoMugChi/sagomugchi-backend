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
    naver_clova_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
