import io

import numpy as np
import pytest
import soundfile as sf

from app.services.voice_features import extract_voice_features


def _sine_wave_bytes(freq_hz: float = 220.0, duration_sec: float = 1.0, sr: int = 22050) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * freq_hz * t)
    buffer = io.BytesIO()
    sf.write(buffer, y, sr, format="WAV")
    return buffer.getvalue()


def test_extract_voice_features_on_pure_tone():
    audio_bytes = _sine_wave_bytes(freq_hz=220.0, duration_sec=1.0)

    features = extract_voice_features(audio_bytes)

    assert features.duration_sec == pytest.approx(1.0, abs=0.05)
    assert features.f0_mean_hz == pytest.approx(220.0, rel=0.1)
    assert features.rms_mean > 0
    assert features.speaking_rate_sps is not None
    assert features.speaking_rate_sps >= 0
