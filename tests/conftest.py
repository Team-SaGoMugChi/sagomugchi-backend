"""테스트 전역 설정.

`.env`에는 실제 CLOVA/LLM 키가 들어 있다. 그래서 모킹을 하나라도 빠뜨리면 pytest가
외부 API를 정말로 호출한다 — 과금되고, 응답이 매번 달라져 단정적인 assert가 흔들린다.
모든 테스트에서 기본값으로 키를 비워 "미설정" 경로를 타게 하고, 외부 호출을 검증하는
테스트만 httpx를 모킹한 뒤 필요한 키를 직접 주입한다(tests/test_stt.py 참고).

get_settings()는 @lru_cache라서 환경변수만 바꿔도 이전 값이 남는다 — 앞뒤로 캐시를 비운다.
"""

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_external_api_keys(monkeypatch):
    for name in ("LLM_API_KEY", "CLOVA_SPEECH_INVOKE_URL", "CLOVA_SPEECH_SECRET"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
