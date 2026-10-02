import pytest
from unittest.mock import Mock

from app.services.text_emotion import KeywordTextEmotionClassifier

import io
import json

import cv2
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import step2 as step2_route
from app.services.face_features import FaceFeatures
from app.services.analysis_media import DailyMultimodalFeatures
from app.services.modality_emotion import FaceEmotion, VoiceArousal
from app.services.multimodal_contract import (
    REQUIRED_FACE_MULTIMODAL_KEYS,
    REQUIRED_VOICE_MULTIMODAL_KEYS,
)
from app.services.text_emotion import EMOTION_LABELS

client = TestClient(app)

_BASELINE_VOICE = {
    "pitchMean": 220.0,
    "f0Std": 28.0,
    "speechRate": 4.0,
    "voicedRatio": 0.61,
    "durationSec": 352.0,
    "energyMean": 0.3,
    **{key: 0.1 for key in REQUIRED_VOICE_MULTIMODAL_KEYS},
    "windowCount": 2.0,
    "windowUsedCount": 2.0,
}
_BASELINE_FACE = {
    "eyeAspectRatio": 0.28,
    "mouthAspectRatio": 0.11,
    "mouthWidthRatio": 1.42,
    "eyebrowRaiseRatio": 0.38,
    **{key: 0.0 for key in REQUIRED_FACE_MULTIMODAL_KEYS},
    "auFrameCount": 1.0,
    "auTotalFrames": 1.0,
}


def _baseline_form(**overrides: str) -> dict[str, str]:
    form = {
        "baseline_voice": json.dumps(_BASELINE_VOICE),
        "baseline_face": json.dumps(_BASELINE_FACE),
        "baseline_feature_version": "2",
        "baseline_measured_at": "2026-09-26T10:09:43.476330Z",
    }
    form.update(overrides)
    return form


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


def test_analyze_step2_returns_fusion_result(monkeypatch):
    multimodal = Mock(wraps=step2_route.extract_daily_multimodal_features)
    monkeypatch.setattr(step2_route, "extract_daily_multimodal_features", multimodal)
    monkeypatch.setattr(
        "app.services.analysis_media.extract_face_features",
        lambda _bytes: FaceFeatures(
            landmarks_detected=True,
            eye_aspect_ratio=0.3,
            mouth_aspect_ratio=0.12,
            mouth_width_ratio=1.5,
            eyebrow_raise_ratio=0.4,
        ),
    )
    response = client.post(
        "/diary/step2/analyze",
        data={
            "text": "오늘 정말 행복하고 기쁜 하루였어",
            **_baseline_form(),
        },
        files=[
            ("voice_file", ("sample.wav", _sine_wave_bytes(freq_hz=320.0), "audio/wav")),
            ("face_images", ("face-1.png", _blank_png_bytes(), "image/png")),
            ("face_images", ("face-2.png", _blank_png_bytes(), "image/png")),
        ],
    )

    assert response.status_code == 200
    assert len(multimodal.call_args.args[1]) == 2
    body = response.json()

    assert body["emotion_keywords"][0] == "기쁨"
    assert 0 <= body["emotion_intensity"] <= 100
    assert "pitchMean" in body["voice_delta"]
    assert body["voice_delta"]["pitchMean"]["baseline_value"] == 220.0
    assert set(body["face_delta"]) == {
        "eyeAspectRatio",
        "mouthAspectRatio",
        "mouthWidthRatio",
        "eyebrowRaiseRatio",
    }
    assert body["modalities"] == ["text", "face", "voice"]
    assert "평소보다 많이 웃음" in body["signals"]


def test_analyze_step2_rejects_capture_without_face():
    response = client.post(
        "/diary/step2/analyze",
        data={"text": "오늘 정말 행복하고 기쁜 하루였어", **_baseline_form()},
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "face_not_detected"
    assert "다시 촬영" in detail["message"]


def test_analyze_step2_rejects_corrupt_recording():
    response = client.post(
        "/diary/step2/analyze",
        data={"text": "오늘 정말 행복하고 기쁜 하루였어", **_baseline_form()},
        files={
            "voice_file": ("sample.wav", b"not-audio", "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_audio"
    assert "다시 녹음" in detail["message"]


def test_analyze_step2_rejects_missing_baseline_contract():
    response = client.post(
        "/diary/step2/analyze",
        data={"text": "너무 불안하고 걱정돼"},
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "baseline_remeasurement_required"
    )


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


def test_analyze_step2_rejects_legacy_baseline_version():
    response = client.post(
        "/diary/step2/analyze",
        data={"text": "테스트", **_baseline_form(baseline_feature_version="0")},
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "baseline_remeasurement_required"
    assert "다시 측정" in detail["message"]


def test_analyze_step2_rejects_incomplete_baseline_values():
    incomplete_voice = dict(_BASELINE_VOICE)
    incomplete_voice.pop("f0Std")
    response = client.post(
        "/diary/step2/analyze",
        data={
            "text": "테스트",
            **_baseline_form(baseline_voice=json.dumps(incomplete_voice)),
        },
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "baseline_remeasurement_required"
    )


def test_analyze_step2_rejects_invalid_multimodal_statistics():
    invalid_voice = dict(_BASELINE_VOICE)
    invalid_voice["windowPitchStd"] = -1.0
    response = client.post(
        "/diary/step2/analyze",
        data={
            "text": "테스트",
            **_baseline_form(baseline_voice=json.dumps(invalid_voice)),
        },
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "baseline_remeasurement_required"


def test_analyze_step2_rejects_non_utc_measurement_time():
    response = client.post(
        "/diary/step2/analyze",
        data={
            "text": "테스트",
            **_baseline_form(baseline_measured_at="2026-09-26T19:09:43+09:00"),
        },
        files={
            "voice_file": ("sample.wav", _sine_wave_bytes(), "audio/wav"),
            "face_image": ("sample.png", _blank_png_bytes(), "image/png"),
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "baseline_remeasurement_required"
    )


@pytest.fixture(autouse=True)
def isolated_text_classifier(monkeypatch):
    monkeypatch.setattr("app.services.fusion.get_text_emotion_classifier", KeywordTextEmotionClassifier)
    monkeypatch.setattr(
        "app.api.routes.step2.extract_daily_multimodal_features",
        lambda *args: DailyMultimodalFeatures(
            face=FaceEmotion(
                scores=dict.fromkeys(EMOTION_LABELS, 0.0),
                valence=0.0,
                z={"au12": 3.0},
            ),
            voice=VoiceArousal(arousal=0.0, z={}),
        ),
    )
