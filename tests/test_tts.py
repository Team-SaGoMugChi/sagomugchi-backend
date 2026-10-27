import base64
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import get_settings


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.mark.parametrize("speaker", ["nara", "njinho", "nminyoung", "ndonghyun"])
def test_four_voices_forwarded_without_persistence(client, speaker):
    settings = get_settings().model_copy(update={"clova_voice_client_id": "test-id", "clova_voice_client_secret": "test-secret"})
    response = httpx.Response(200, content=b"audio", headers={"content-type": "audio/mpeg"}, request=httpx.Request("POST", "https://example.test"))
    with patch("app.api.routes.tts.get_settings", return_value=settings), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response) as post:
        result = client.post("/tts", json={"text": "안녕하세요", "speaker": speaker})
    assert result.status_code == 200
    assert base64.b64decode(result.json()["audio_base64"]) == b"audio"
    assert post.call_args.kwargs["data"]["speaker"] == speaker


@pytest.mark.parametrize("payload", [{"text": " "}, {"text": "a" * 2001}, {"text": "hello", "speaker": "unknown"}])
def test_invalid_input_rejected(client, payload):
    assert client.post("/tts", json=payload).status_code == 422


def test_missing_configuration_is_explicit(client):
    settings = get_settings().model_copy(update={"clova_voice_client_id": None, "clova_voice_client_secret": None})
    with patch("app.api.routes.tts.get_settings", return_value=settings):
        assert client.post("/tts", json={"text": "hello"}).status_code == 503


def test_provider_errors_do_not_expose_text_or_keys(client):
    settings = get_settings().model_copy(update={"clova_voice_client_id": "test-id", "clova_voice_client_secret": "test-secret"})
    with patch("app.api.routes.tts.get_settings", return_value=settings), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("private-provider-error")):
        result = client.post("/tts", json={"text": "hello"})
    assert result.status_code == 502
    assert "private-provider-error" not in result.text
    assert "test-secret" not in result.text
