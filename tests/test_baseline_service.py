import io
from dataclasses import replace

import cv2
import numpy as np
import pytest
import soundfile as sf

from app.services.baseline_service import BaselineMeasurementError, build_baseline_profile
from app.services.face_features import FaceFeatures
from app.services.voice_features import VoiceFeatures


@pytest.fixture
def valid_face(monkeypatch):
    features = FaceFeatures(True, 0.28, 0.1, 0.8, 0.3)
    monkeypatch.setattr("app.services.baseline_service.extract_face_features", lambda _: features)
    return features


@pytest.fixture
def valid_voice(monkeypatch):
    features = VoiceFeatures(1.0, 220.0, 1.0, 0.8, 0.3, 0.1, 3.0)
    monkeypatch.setattr("app.services.baseline_service.extract_voice_features", lambda _: features)
    return features


def _wav_bytes(samples):
    buffer = io.BytesIO()
    sf.write(buffer, samples, 22050, format="WAV")
    return buffer.getvalue()


def test_build_baseline_profile_maps_features_to_schema_keys(valid_face):
    t = np.arange(22050) / 22050
    profile = build_baseline_profile("user-1", _wav_bytes(0.5 * np.sin(2 * np.pi * 220 * t)), b"face")
    assert profile.user_id == "user-1"
    assert profile.measured_at
    assert profile.voice.keys() >= {"pitchMean", "energyMean", "speechRate"}
    assert profile.voice["pitchMean"] == pytest.approx(220.0, rel=0.1)
    assert profile.voice["energyMean"] > 0
    assert profile.face == {"eyeAspectRatio": 0.28, "mouthAspectRatio": 0.1,
                            "mouthWidthRatio": 0.8, "eyebrowRaiseRatio": 0.3}


@pytest.mark.parametrize("samples", [np.zeros(22050), np.array([])])
def test_rejects_silent_or_empty_recording(samples, valid_face):
    with pytest.raises(BaselineMeasurementError, match="목소리"):
        build_baseline_profile("user-1", _wav_bytes(samples), b"face")


@pytest.mark.parametrize("audio", [b"", b"not an audio file"])
def test_rejects_unreadable_audio(audio, valid_face):
    with pytest.raises(BaselineMeasurementError) as error:
        build_baseline_profile("user-1", audio, b"face")
    assert error.value.code == "invalid_audio"


@pytest.mark.parametrize("face", [b"", b"not an image", cv2.imencode(".png", np.zeros((100, 100, 3), np.uint8))[1].tobytes()])
def test_rejects_missing_face(face, valid_voice):
    with pytest.raises(BaselineMeasurementError) as error:
        build_baseline_profile("user-1", b"voice", face)
    assert error.value.code in {"invalid_face_image", "face_not_detected"}


@pytest.mark.parametrize("field,value", [("f0_mean_hz", None), ("f0_mean_hz", float("nan")),
                                         ("rms_mean", float("inf")), ("voiced_ratio", 0.0)])
def test_rejects_unusable_voice_features(monkeypatch, valid_voice, valid_face, field, value):
    monkeypatch.setattr("app.services.baseline_service.extract_voice_features",
                        lambda _: replace(valid_voice, **{field: value}))
    with pytest.raises(BaselineMeasurementError) as error:
        build_baseline_profile("user-1", b"voice", b"face")
    assert error.value.code == "voice_not_detected"


def test_rejects_nonfinite_face_features(monkeypatch, valid_voice, valid_face):
    monkeypatch.setattr("app.services.baseline_service.extract_face_features",
                        lambda _: replace(valid_face, eye_aspect_ratio=float("nan")))
    with pytest.raises(BaselineMeasurementError) as error:
        build_baseline_profile("user-1", b"voice", b"face")
    assert error.value.code == "face_not_detected"
