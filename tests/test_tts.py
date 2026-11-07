import base64
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes.tts import FISH_URL, FISH_VOICES, fish_speed
from app.main import create_app
from app.core.config import get_settings

CLOVA_ONLY = {"clova_voice_client_id": "test-id", "clova_voice_client_secret": "test-secret", "fish_api_key": None}
FISH_ONLY = {"clova_voice_client_id": None, "clova_voice_client_secret": None, "fish_api_key": "fish-secret"}
BOTH = {**CLOVA_ONLY, "fish_api_key": "fish-secret"}


def _settings(update):
    return get_settings().model_copy(update=update)


def _audio(content=b"audio", status=200, content_type="audio/mpeg"):
    return httpx.Response(status, content=content, headers={"content-type": content_type}, request=httpx.Request("POST", "https://example.test"))


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.mark.parametrize("speaker", ["nara", "njinho", "nminyoung", "ndonghyun"])
def test_four_voices_forwarded_without_persistence(client, speaker):
    with patch("app.api.routes.tts.get_settings", return_value=_settings(CLOVA_ONLY)), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_audio()) as post:
        result = client.post("/tts", json={"text": "안녕하세요", "speaker": speaker})
    assert result.status_code == 200
    assert base64.b64decode(result.json()["audio_base64"]) == b"audio"
    assert post.call_args.kwargs["data"]["speaker"] == speaker
    assert post.call_args.kwargs["data"]["speed"] == "0"


def test_speed_forwarded_when_given(client):
    with patch("app.api.routes.tts.get_settings", return_value=_settings(CLOVA_ONLY)), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_audio()) as post:
        result = client.post("/tts", json={"text": "안녕하세요", "speed": -2})
    assert result.status_code == 200
    assert post.call_args.kwargs["data"]["speed"] == "-2"


@pytest.mark.parametrize(
    "payload",
    [{"text": " "}, {"text": "a" * 2001}, {"text": "hello", "speaker": "unknown"}, {"text": "hello", "speed": -6}, {"text": "hello", "speed": 6}],
)
def test_invalid_input_rejected(client, payload):
    assert client.post("/tts", json=payload).status_code == 422


def test_missing_configuration_is_explicit(client):
    settings = _settings({"clova_voice_client_id": None, "clova_voice_client_secret": None, "fish_api_key": None})
    with patch("app.api.routes.tts.get_settings", return_value=settings):
        assert client.post("/tts", json={"text": "hello"}).status_code == 503


def test_provider_errors_do_not_expose_text_or_keys(client):
    with patch("app.api.routes.tts.get_settings", return_value=_settings(BOTH)), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("private-provider-error")):
        result = client.post("/tts", json={"text": "hello"})
    assert result.status_code == 502
    assert "private-provider-error" not in result.text
    assert "test-secret" not in result.text
    assert "fish-secret" not in result.text


def test_each_tone_has_its_own_fish_voice():
    assert set(FISH_VOICES) == {"nara", "njinho", "nminyoung", "ndonghyun"}
    assert len(set(FISH_VOICES.values())) == 4


@pytest.mark.parametrize("speaker", ["nara", "njinho", "nminyoung", "ndonghyun"])
def test_fish_used_when_key_set(client, speaker):
    with patch("app.api.routes.tts.get_settings", return_value=_settings(BOTH)), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_audio(b"fish")) as post:
        result = client.post("/tts", json={"text": "안녕하세요", "speaker": speaker, "speed": -2})
    assert result.status_code == 200
    assert base64.b64decode(result.json()["audio_base64"]) == b"fish"
    assert post.await_count == 1
    assert post.call_args.args[0] == FISH_URL
    body = post.call_args.kwargs["json"]
    assert body["reference_id"] == FISH_VOICES[speaker]
    assert body["prosody"] == {"speed": 1.2}
    assert post.call_args.kwargs["headers"]["model"] == "s2.1-pro-free"


def test_fish_alone_is_enough(client):
    with patch("app.api.routes.tts.get_settings", return_value=_settings(FISH_ONLY)), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_audio()):
        assert client.post("/tts", json={"text": "hello"}).status_code == 200


@pytest.mark.parametrize("failure", [_audio(b"", status=402, content_type="application/json"), httpx.ConnectError("down")])
def test_falls_back_to_clova_when_fish_fails(client, failure):
    with patch("app.api.routes.tts.get_settings", return_value=_settings(BOTH)), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=[failure, _audio(b"clova")]) as post:
        result = client.post("/tts", json={"text": "hello", "speaker": "njinho"})
    assert result.status_code == 200
    assert base64.b64decode(result.json()["audio_base64"]) == b"clova"
    assert post.call_args.kwargs["data"]["speaker"] == "njinho"


def test_fish_non_audio_response_is_rejected(client):
    with patch("app.api.routes.tts.get_settings", return_value=_settings(FISH_ONLY)), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_audio(b"{}", content_type="application/json")):
        assert client.post("/tts", json={"text": "hello"}).status_code == 502


@pytest.mark.parametrize(("clova", "fish"), [(0, 1.0), (-2, 1.2), (-5, 1.5), (5, 0.5)])
def test_fish_speed_matches_clova_scale(clova, fish):
    assert fish_speed(clova) == fish
