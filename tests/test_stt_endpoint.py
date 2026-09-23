"""POST /stt/transcribe 테스트 — 서비스 계층은 모킹하고 HTTP 계약만 검증한다."""

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.stt import SttError, SttResult

client = TestClient(app)


def _upload(data: bytes = b"fake-wav-bytes"):
    # 필드명 voice_file은 앱이 쓰는 이름 — 바뀌면 프론트가 깨진다.
    return {"voice_file": ("step1.wav", io.BytesIO(data), "audio/wav")}


def test_transcribe_returns_recognized_text(monkeypatch):
    async def fake_transcribe(audio_bytes, filename="audio.wav"):
        return SttResult(text="오늘은 행복했어요", confidence=0.9, duration_ms=3260, word_count=3)

    monkeypatch.setattr("app.api.routes.stt.transcribe_audio", fake_transcribe)

    response = client.post("/stt/transcribe", files=_upload())

    assert response.status_code == 200
    assert response.json() == {
        "text": "오늘은 행복했어요",
        "confidence": 0.9,
        "duration_ms": 3260,
        "word_count": 3,
    }


def test_missing_keys_returns_503_without_calling_clova():
    # conftest가 CLOVA 키를 비워두므로 외부 호출 없이 stt_not_configured로 떨어진다.
    # 키 없는 팀원 로컬에서 이 엔드포인트를 불렀을 때의 동작이다.
    response = client.post("/stt/transcribe", files=_upload())

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "stt_not_configured"


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        ("invalid_audio", 422),  # 앱이 재녹음을 안내해야 하는 경우
        ("speech_not_recognized", 422),
        ("stt_unavailable", 502),  # 같은 파일로 재시도 가능
    ],
)
def test_service_errors_map_to_status_codes(monkeypatch, code, expected_status):
    async def fake_transcribe(audio_bytes, filename="audio.wav"):
        raise SttError(code, "테스트 메시지")

    monkeypatch.setattr("app.api.routes.stt.transcribe_audio", fake_transcribe)

    response = client.post("/stt/transcribe", files=_upload())

    assert response.status_code == expected_status
    assert response.json()["detail"] == {"code": code, "message": "테스트 메시지"}


def test_missing_file_returns_422():
    response = client.post("/stt/transcribe")

    assert response.status_code == 422
