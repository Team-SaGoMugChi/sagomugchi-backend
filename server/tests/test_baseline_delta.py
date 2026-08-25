import pytest

from app.services.baseline_delta import compute_face_delta, compute_voice_delta
from app.services.face_features import FaceFeatures
from app.services.voice_features import VoiceFeatures


def test_compute_voice_delta_basic():
    baseline = {"pitchMean": 200.0, "energyMean": 0.1, "speechRate": 3.0}
    current = VoiceFeatures(
        duration_sec=1.0,
        f0_mean_hz=220.0,
        f0_std_hz=5.0,
        voiced_ratio=0.9,
        rms_mean=0.15,
        rms_std=0.02,
        speaking_rate_sps=3.6,
    )

    deltas = compute_voice_delta(baseline, current)

    assert set(deltas.keys()) == {"pitchMean", "energyMean", "speechRate"}
    assert deltas["pitchMean"].delta == pytest.approx(20.0)
    assert deltas["pitchMean"].relative_delta == pytest.approx(0.1)
    assert deltas["energyMean"].delta == pytest.approx(0.05, abs=1e-9)


def test_compute_voice_delta_skips_keys_missing_from_baseline():
    baseline: dict[str, float] = {}  # baseline 저장 당시 값이 없었던 경우
    current = VoiceFeatures(
        duration_sec=1.0,
        f0_mean_hz=220.0,
        f0_std_hz=None,
        voiced_ratio=1.0,
        rms_mean=0.1,
        rms_std=0.0,
        speaking_rate_sps=3.0,
    )

    deltas = compute_voice_delta(baseline, current)

    assert deltas == {}


def test_compute_face_delta_zero_baseline_gives_no_relative_delta():
    baseline = {"eyeAspectRatio": 0.0, "mouthAspectRatio": 0.1, "mouthWidthRatio": 0.5, "eyebrowRaiseRatio": 0.2}
    current = FaceFeatures(
        landmarks_detected=True,
        eye_aspect_ratio=0.3,
        mouth_aspect_ratio=0.2,
        mouth_width_ratio=0.6,
        eyebrow_raise_ratio=0.3,
    )

    deltas = compute_face_delta(baseline, current)

    assert deltas["eyeAspectRatio"].delta == pytest.approx(0.3)
    assert deltas["eyeAspectRatio"].relative_delta is None
    assert deltas["mouthAspectRatio"].relative_delta == pytest.approx(1.0)


def test_compute_face_delta_no_landmarks_detected_yields_empty():
    baseline = {"eyeAspectRatio": 0.3}
    current = FaceFeatures(
        landmarks_detected=False,
        eye_aspect_ratio=None,
        mouth_aspect_ratio=None,
        mouth_width_ratio=None,
        eyebrow_raise_ratio=None,
    )

    deltas = compute_face_delta(baseline, current)

    assert deltas == {}
