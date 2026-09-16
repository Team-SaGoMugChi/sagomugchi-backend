import pytest

from app.services.text_emotion import KeywordTextEmotionClassifier

import io
import json

import cv2
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _sine_wave_bytes(freq_hz: float = 220.0, duration_sec: float = 1.0, sr: int = 22050) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * freq_hz * t)
    buffer = io.BytesIO()
    sf.write(buffer, y, sr, format="WAV")
    return buffer.getvalue()


def _blank_png_bytes() -> bytes:
    image = np.full((240, 320, 3), 128, dtype=np.uint8)
    _success, encoded = cv2.imencode(".png", image)
    return encoded.tobytes()


def test_analyze_step2_returns_fusion_result():
    baseline_voice = json.dumps({"pitchMean": 220.0, "energyMean": 0.3, "speechRate": 4.0})

    response = client.post(
        "/diary/step2/analyze",
        data={
            "text": "오늘 정말 행복하고 기쁜 하루였어",
            "baseline_voice": baseline_voice,
            "baseline_face": "{}",
        },
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(freq_hz=320.0), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["emotion_keywords"][0] == "기쁨"
    assert 0 <= body["emotion_intensity"] <= 100
    assert "pitchMean" in body["voice_delta"]
    assert body["voice_delta"]["pitchMean"]["baseline_value"] == 220.0
    assert body["face_delta"] == {}


def test_analyze_step2_defaults_to_empty_baseline_when_omitted():
    response = client.post(
        "/diary/step2/analyze",
        data={"text": "너무 불안하고 걱정돼"},
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["emotion_keywords"][0] == "불안"
    assert body["voice_delta"] == {}


def test_analyze_step2_rejects_invalid_baseline_json():
    response = client.post(
        "/diary/step2/analyze",
        data={"text": "테스트", "baseline_voice": "not-json"},
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 422


@pytest.fixture(autouse=True)
def isolated_text_classifier(monkeypatch):
    monkeypatch.setattr("app.services.fusion.get_text_emotion_classifier", KeywordTextEmotionClassifier)
