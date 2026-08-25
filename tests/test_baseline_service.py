import io

import cv2
import numpy as np
import pytest
import soundfile as sf

from app.services.baseline_service import build_baseline_profile


def _sine_wave_bytes(freq_hz: float = 220.0, duration_sec: float = 1.0, sr: int = 22050) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * freq_hz * t)
    buffer = io.BytesIO()
    sf.write(buffer, y, sr, format="WAV")
    return buffer.getvalue()


def _blank_image_bytes() -> bytes:
    image = np.full((240, 320, 3), 128, dtype=np.uint8)
    _success, encoded = cv2.imencode(".png", image)
    return encoded.tobytes()


def test_build_baseline_profile_maps_features_to_schema_keys():
    profile = build_baseline_profile(
        user_id="user-1",
        voice_bytes=_sine_wave_bytes(),
        face_image_bytes=_blank_image_bytes(),
    )

    assert profile.user_id == "user-1"
    assert profile.measured_at  # ISO-8601 문자열, 비어있지 않음

    # FIRESTORE_SCHEMA.md §2가 예시로 든 키(pitchMean, speechRate, energyMean)와 일치해야 함
    assert profile.voice.keys() >= {"pitchMean", "energyMean"}
    assert profile.voice["pitchMean"] == pytest.approx(220.0, rel=0.1)
    assert profile.voice["energyMean"] > 0

    # 얼굴 없는 이미지라 face 맵은 비어 있어야 함
    assert profile.face == {}
