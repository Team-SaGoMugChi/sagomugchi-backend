import io

import numpy as np
import pytest
import soundfile as sf

from app.services.voice_windows import (
    VoiceWindow,
    analyze_windows,
    split_windows,
    summarize_windows,
)

_SR = 22050


def _tone(freq_hz: float, duration_sec: float) -> np.ndarray:
    t = np.linspace(0, duration_sec, int(_SR * duration_sec), endpoint=False)
    return 0.5 * np.sin(2 * np.pi * freq_hz * t)


def _wav_bytes(y: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, y, _SR, format="WAV")
    return buffer.getvalue()


def test_split_drops_only_a_short_tail():
    y = np.zeros(int(_SR * 7.0))  # 3초 + 3초 + 1초 자투리(1.5초 미만)

    windows = split_windows(y, _SR, window_sec=3.0)

    assert [start for start, _ in windows] == [0.0, 3.0]


def test_split_keeps_a_tail_of_at_least_half_a_window():
    y = np.zeros(int(_SR * 4.5))

    assert len(split_windows(y, _SR, window_sec=3.0)) == 2


def test_windows_follow_pitch_changes_and_skip_silence():
    y = np.concatenate([_tone(150.0, 3.0), _tone(200.0, 3.0), np.zeros(int(_SR * 3.0))])

    windows = analyze_windows(_wav_bytes(y))
    summary = summarize_windows(windows)

    assert len(windows) == 3
    assert windows[0].pitch_mean == pytest.approx(150.0, rel=0.05)
    assert windows[1].pitch_mean == pytest.approx(200.0, rel=0.05)
    assert windows[2].voiced_ratio < 0.2
    # 무음 구간은 요약에서 빠진다
    assert summary.window_count == 3
    assert summary.used_count == 2
    assert summary.mean["pitchMean"] == pytest.approx(175.0, rel=0.05)
    assert summary.std["pitchMean"] == pytest.approx(25.0, rel=0.15)


def _window(voiced_ratio: float, pitch: float | None, energy: float, rate: float | None) -> VoiceWindow:
    return VoiceWindow(
        start_sec=0.0,
        duration_sec=3.0,
        voiced_ratio=voiced_ratio,
        pitch_mean=pitch,
        energy_mean=energy,
        speech_rate=rate,
    )


def test_summary_uses_feature_map_keys_and_population_std():
    summary = summarize_windows([_window(0.8, 200.0, 0.1, 4.0), _window(0.6, 220.0, 0.3, 5.0)])

    assert summary.mean == pytest.approx({"pitchMean": 210.0, "energyMean": 0.2, "speechRate": 4.5})
    assert summary.std == pytest.approx({"pitchMean": 10.0, "energyMean": 0.1, "speechRate": 0.5})


def test_summary_without_speech_is_empty():
    summary = summarize_windows([_window(0.0, None, 0.0, 0.0)])

    assert summary.used_count == 0
    assert summary.mean == {}
    assert summary.std == {}
