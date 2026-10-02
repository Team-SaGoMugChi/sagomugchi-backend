import io
from dataclasses import replace
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import soundfile as sf

from app.services.baseline_service import BaselineMeasurementError, build_baseline_profile
from app.services.face_features import FaceFeatures
from app.services.face_au import FaceAu
from app.services.voice_features import VoiceFeatures
from app.services.voice_windows import VoiceWindow


@pytest.fixture
def valid_face(monkeypatch):
    features = FaceFeatures(True, 0.28, 0.1, 0.8, 0.3)
    monkeypatch.setattr("app.services.baseline_service.extract_face_features", lambda _: features)
    face_au = FaceAu(True, {
        "au1": 0.01, "au2": 0.01, "au4": 0.01, "au5": 0.01,
        "au6": 0.01, "au7": 0.01, "au12": 0.01, "au15": 0.01, "au17": 0.01,
    })
    monkeypatch.setattr(
        "app.services.baseline_service.get_face_au_extractor",
        lambda: SimpleNamespace(extract=lambda _: face_au),
    )
    return features


@pytest.fixture
def valid_voice(monkeypatch):
    features = VoiceFeatures(1.0, 220.0, 1.0, 0.8, 0.3, 0.1, 3.0)
    monkeypatch.setattr("app.services.baseline_service.extract_voice_features", lambda _: features)
    monkeypatch.setattr(
        "app.services.baseline_service.analyze_windows",
        lambda _: [VoiceWindow(0.0, 3.0, 0.8, 220.0, 0.1, 3.0)],
    )
    return features


def _wav_bytes(samples):
    buffer = io.BytesIO()
    sf.write(buffer, samples, 22050, format="WAV")
    return buffer.getvalue()


def test_build_baseline_profile_maps_features_to_schema_keys(valid_face):
    t = np.arange(22050 * 3) / 22050
    profile = build_baseline_profile("user-1", _wav_bytes(0.5 * np.sin(2 * np.pi * 220 * t)), b"face")
    assert profile.user_id == "user-1"
    assert profile.feature_version == 2
    assert profile.voice["durationSec"] == pytest.approx(3.0)
    assert 0 < profile.voice["voicedRatio"] <= 1
    assert profile.voice["f0Std"] >= 0
    assert profile.measured_at
    assert profile.voice.keys() >= {"pitchMean", "energyMean", "speechRate"}
    assert profile.voice["pitchMean"] == pytest.approx(220.0, rel=0.1)
    assert profile.voice["energyMean"] > 0
    assert profile.face.items() >= {"eyeAspectRatio": 0.28, "mouthAspectRatio": 0.1,
                                    "mouthWidthRatio": 0.8, "eyebrowRaiseRatio": 0.3}.items()
    assert "au12LogMean" in profile.face
    assert "windowPitchMean" in profile.voice


def test_build_baseline_profile_summarizes_multiple_face_frames(
    monkeypatch, valid_voice, valid_face
):
    values = iter((0.01, 0.1, 0.4))

    def extract(_):
        value = next(values)
        return FaceAu(True, {
            "au1": value, "au2": value, "au4": value, "au5": value,
            "au6": value, "au7": value, "au12": value, "au15": value,
            "au17": value,
        })

    monkeypatch.setattr(
        "app.services.baseline_service.get_face_au_extractor",
        lambda: SimpleNamespace(extract=extract),
    )

    profile = build_baseline_profile(
        "user-1", b"voice", [b"face-1", b"face-2", b"face-3"]
    )

    assert profile.face["auFrameCount"] == 3
    assert profile.face["auTotalFrames"] == 3
    assert profile.face["au12LogStd"] > 0


def test_build_baseline_profile_uses_later_detected_face(monkeypatch, valid_voice, valid_face):
    def extract(frame):
        if frame == b"missed":
            return FaceFeatures(False, None, None, None, None)
        return valid_face

    monkeypatch.setattr("app.services.baseline_service.extract_face_features", extract)
    profile = build_baseline_profile("user-1", b"voice", [b"missed", b"face"])

    assert profile.face["eyeAspectRatio"] == 0.28
    assert profile.face["auTotalFrames"] == 2


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
                                         ("rms_mean", float("inf")), ("voiced_ratio", 0.0),
                                         ("voiced_ratio", 1.1), ("f0_std_hz", None),
                                         ("f0_std_hz", -1.0), ("f0_std_hz", float("nan")),
                                         ("duration_sec", float("inf"))])
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


def test_handoff_fields_survive_firestore_save(monkeypatch, valid_voice, valid_face):
    from app.services import baseline_repository
    from tests.test_baseline_repository import _FakeFirestoreClient
    from app.services.baseline_delta import compute_voice_delta

    client = _FakeFirestoreClient()
    monkeypatch.setattr(baseline_repository, "get_firestore_client", lambda: client)
    profile = build_baseline_profile("handoff-user", b"voice", b"face")
    baseline_repository.save_baseline_profile(profile)
    saved = client.collection("users").document("handoff-user").collection("meta").document("baseline").set_calls[0]
    assert saved["featureVersion"] == 2
    assert saved["voice"]["f0Std"] == 1.0
    assert saved["voice"]["voicedRatio"] == 0.8
    assert saved["voice"]["durationSec"] == 1.0
    assert profile.model_dump()["feature_version"] == 2
    # Metadata must not become additional terms in the existing emotion score.
    assert set(compute_voice_delta(saved["voice"], valid_voice)) == {"pitchMean", "energyMean", "speechRate"}
