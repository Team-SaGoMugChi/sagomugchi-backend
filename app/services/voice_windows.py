"""녹음을 일정 길이 구간으로 나눠 구간별 음성 특징과 구간 간 평균·표준편차를 낸다.

논문 식 (1)의 z-score, (현재 − μ_baseline) / σ_baseline에서 σ를 얻기 위한 레이어다.
기존 baseline의 f0Std는 프레임(수십 ms) 단위 흔들림이라, 녹음 전체의 평균 피치를 비교할
기준으로 쓰면 너무 커서 거의 모든 변화가 0에 가깝게 눌린다. 그래서 "몇 초 단위로 말할 때
평소 얼마나 흔들리는가"를 따로 잰다. 같은 구간 값들은 나중에 실시간 분석에서도 그대로 쓸
수 있다.

피치·에너지·속도 계산은 voice_features.py 함수를 그대로 써서 baseline과 계산 방식이
어긋나지 않게 한다. 유성음이 거의 없는 구간(쉼, 숨 고르기)은 요약에서 뺀다 — 말을 멈춘
시간이 에너지 평균을 끌어내려 감정 변화처럼 보이는 것을 막기 위해서다.

baseline 저장 키(feature_maps)와 fusion 연결은 팀 합의 후 별도로 붙인다.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.services.voice_features import estimate_speaking_rate, extract_f0, extract_rms, load_audio

WINDOW_SEC = 3.0
# 구간 안에서 유성음 프레임이 이보다 적으면 말하지 않은 구간으로 본다.
MIN_VOICED_RATIO = 0.2
# 마지막 자투리 구간은 이 비율 이상 길이일 때만 쓴다 — 너무 짧으면 속도 추정이 튄다.
_MIN_TAIL_RATIO = 0.5

# 요약 키는 feature_maps.voice_features_to_map과 같은 이름을 쓴다.
VOICE_WINDOW_KEYS = ("pitchMean", "energyMean", "speechRate")


@dataclass
class VoiceWindow:
    start_sec: float
    duration_sec: float
    voiced_ratio: float
    pitch_mean: float | None  # Hz. 유성음이 없으면 None
    energy_mean: float
    speech_rate: float | None  # 음절/초 근사치


@dataclass
class VoiceWindowSummary:
    """말한 구간들의 특징별 평균·표준편차. 표준편차는 모집단 기준(ddof=0) — f0Std와 같은 규칙."""

    window_count: int  # 나눈 구간 수
    used_count: int  # 말한 구간으로 판정돼 요약에 쓰인 수
    mean: dict[str, float]
    std: dict[str, float]


def split_windows(y: np.ndarray, sr: int, window_sec: float = WINDOW_SEC) -> list[tuple[float, np.ndarray]]:
    """(시작 초, 구간 샘플) 목록. 짧은 자투리 끝 구간은 버린다."""
    size = int(window_sec * sr)
    if size <= 0:
        raise ValueError("window_sec must be positive")
    windows = []
    for start in range(0, len(y), size):
        segment = y[start:start + size]
        if len(segment) < size * _MIN_TAIL_RATIO:
            break
        windows.append((start / sr, segment))
    return windows


def analyze_segment(start_sec: float, segment: np.ndarray, sr: int) -> VoiceWindow:
    duration_sec = len(segment) / sr
    f0, voiced_flag = extract_f0(segment, sr)
    voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
    voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None and voiced_flag.size > 0 else 0.0
    return VoiceWindow(
        start_sec=start_sec,
        duration_sec=duration_sec,
        voiced_ratio=voiced_ratio,
        pitch_mean=float(np.mean(voiced_f0)) if voiced_f0.size > 0 else None,
        energy_mean=float(np.mean(extract_rms(segment))),
        speech_rate=estimate_speaking_rate(segment, sr, duration_sec),
    )


def analyze_windows(audio_bytes: bytes, window_sec: float = WINDOW_SEC) -> list[VoiceWindow]:
    y, sr = load_audio(audio_bytes)
    return [analyze_segment(start, segment, sr) for start, segment in split_windows(y, sr, window_sec)]


def summarize_windows(windows: Sequence[VoiceWindow]) -> VoiceWindowSummary:
    """말한 구간만으로 특징별 평균·표준편차를 낸다. 값이 없는 특징은 결과에서 빠진다."""
    spoken = [w for w in windows if w.voiced_ratio >= MIN_VOICED_RATIO]
    values = {
        "pitchMean": [w.pitch_mean for w in spoken if w.pitch_mean is not None],
        "energyMean": [w.energy_mean for w in spoken],
        "speechRate": [w.speech_rate for w in spoken if w.speech_rate is not None],
    }
    mean = {key: float(np.mean(v)) for key, v in values.items() if v}
    std = {key: float(np.std(v)) for key, v in values.items() if v}
    return VoiceWindowSummary(window_count=len(windows), used_count=len(spoken), mean=mean, std=std)
