"""app/services/stt.py 테스트 — 실제 CLOVA는 호출하지 않고 httpx를 모킹한다.

실호출을 하면 과금되고 인식 결과가 매번 달라져서 테스트가 불안정해진다. 대신
_SUCCESS_PAYLOAD는 2026-09-21에 실제 도메인(oddo-stt)이 돌려준 응답을 줄인 것이라,
필드 이름과 구조는 진짜와 같다.
"""

import asyncio
import json

import httpx
import pytest

from app.core.config import get_settings
from app.services.stt import SttError, transcribe_audio

_AUDIO = b"fake-wav-bytes"

# 실제 CLOVA 응답에서 검증에 필요한 필드만 남긴 것.
_SUCCESS_PAYLOAD = {
    "result": "COMPLETED",
    "message": "Succeeded",
    "text": "오늘은 정말 행복하고 신나는 하루였어요.",
    "confidence": 0.8957,
    "segments": [
        {
            "start": 0,
            "end": 4228,
            "text": "오늘은 정말 행복하고 신나는 하루였어요.",
            "words": [
                [110, 460, "오늘은"],
                [710, 1000, "정말"],
                [1270, 1860, "행복하고"],
                [2030, 2400, "신나는"],
                [2550, 3260, "하루였어요."],
            ],
        }
    ],
}


@pytest.fixture
def clova_configured(monkeypatch):
    monkeypatch.setenv("CLOVA_SPEECH_INVOKE_URL", "https://clovaspeech-gw.example.com/external/v1/1/abc")
    monkeypatch.setenv("CLOVA_SPEECH_SECRET", "test-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _patch_post(monkeypatch, response=None, raises=None):
    """httpx.AsyncClient.post를 대체하고, 실제로 보낸 인자를 담아 돌려준다."""
    sent: dict[str, object] = {}

    async def fake_post(self, url, **kwargs):
        sent["url"] = url
        sent["headers"] = kwargs.get("headers")
        sent["files"] = kwargs.get("files")
        if raises is not None:
            raise raises
        return response

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return sent


def _sent_params(sent: dict) -> dict:
    """요청의 params 파트(멀티파트 JSON)를 파싱한다."""
    _filename, raw, _content_type = sent["files"]["params"]
    return json.loads(raw)


def test_transcribe_parses_clova_response(monkeypatch, clova_configured):
    _patch_post(monkeypatch, response=httpx.Response(200, json=_SUCCESS_PAYLOAD))

    result = asyncio.run(transcribe_audio(_AUDIO, filename="step1.wav"))

    assert result.text == "오늘은 정말 행복하고 신나는 하루였어요."
    assert result.confidence == pytest.approx(0.8957)
    assert result.duration_ms == 4228  # 세그먼트 끝 시각
    assert result.word_count == 5


def test_transcribe_disables_diarization(monkeypatch, clova_configured):
    # diarization을 명시하지 않으면 CLOVA가 400 "speaker detect is off"를 돌려준다.
    # 2026-09-21에 실제로 막혔던 지점이라 회귀로 고정한다.
    sent = _patch_post(monkeypatch, response=httpx.Response(200, json=_SUCCESS_PAYLOAD))

    asyncio.run(transcribe_audio(_AUDIO))

    params = _sent_params(sent)
    assert params["diarization"] == {"enable": False}
    assert params["language"] == "ko-KR"
    assert params["completion"] == "sync"


def test_transcribe_sends_secret_in_header_and_uses_upload_path(monkeypatch, clova_configured):
    sent = _patch_post(monkeypatch, response=httpx.Response(200, json=_SUCCESS_PAYLOAD))

    asyncio.run(transcribe_audio(_AUDIO))

    assert sent["headers"]["X-CLOVASPEECH-API-KEY"] == "test-secret"
    assert sent["url"].endswith("/recognizer/upload")


def test_transcribe_raises_when_keys_missing():
    # conftest가 키를 비워둔 상태 — 외부 호출 없이 바로 떨어져야 한다.
    with pytest.raises(SttError) as exc_info:
        asyncio.run(transcribe_audio(_AUDIO))

    assert exc_info.value.code == "stt_not_configured"


def test_transcribe_raises_on_empty_audio(clova_configured):
    with pytest.raises(SttError) as exc_info:
        asyncio.run(transcribe_audio(b""))

    assert exc_info.value.code == "invalid_audio"


def test_transcribe_raises_when_no_speech_recognized(monkeypatch, clova_configured):
    # 무음/잡음만 들어간 녹음은 200이지만 text가 빈 문자열로 온다.
    empty = {**_SUCCESS_PAYLOAD, "text": "", "segments": []}
    _patch_post(monkeypatch, response=httpx.Response(200, json=empty))

    with pytest.raises(SttError) as exc_info:
        asyncio.run(transcribe_audio(_AUDIO))

    assert exc_info.value.code == "speech_not_recognized"


def test_transcribe_raises_on_error_status(monkeypatch, clova_configured):
    body = {"result": "ERROR_REQUEST_PARAMETER", "message": "speaker detect is off"}
    _patch_post(monkeypatch, response=httpx.Response(400, json=body))

    with pytest.raises(SttError) as exc_info:
        asyncio.run(transcribe_audio(_AUDIO))

    assert exc_info.value.code == "stt_unavailable"


def test_transcribe_raises_on_connection_error(monkeypatch, clova_configured):
    _patch_post(monkeypatch, raises=httpx.ConnectError("연결 실패"))

    with pytest.raises(SttError) as exc_info:
        asyncio.run(transcribe_audio(_AUDIO))

    assert exc_info.value.code == "stt_unavailable"


def test_transcribe_falls_back_to_whitespace_word_count(monkeypatch, clova_configured):
    # words가 없는 응답에서도 word_count가 0이 되지 않아야 한다.
    no_words = {**_SUCCESS_PAYLOAD, "segments": [{"start": 0, "end": 1000, "text": "가 나 다"}]}
    _patch_post(monkeypatch, response=httpx.Response(200, json=no_words))

    result = asyncio.run(transcribe_audio(_AUDIO))

    assert result.word_count == 5  # "오늘은 정말 행복하고 신나는 하루였어요." 공백 분리
