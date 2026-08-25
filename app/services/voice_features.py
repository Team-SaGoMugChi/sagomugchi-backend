"""librosa 기반 저수준 음성 특징 추출 (F0, RMS, 발화 속도).

baseline 측정과 일기 Step1 음성 분석이 공통으로 쓰는 추출 함수 모음.
API 응답 스키마(app/models/voice.py)와는 분리된, 순수 계산 레이어.
"""

import io
from dataclasses import dataclass

import librosa
import numpy as np
from scipy.signal import find_peaks

_PITCH_FMIN_HZ = 65.0  # 성인 남성 하한 근사
_PITCH_FMAX_HZ = 400.0  # 성인 여성 상한 근사
_HOP_LENGTH = 512
_MIN_SYLLABLE_INTERVAL_SEC = 0.15  # 음절 핵 사이 최소 간격(생리적 상한 ~6~7음절/초 근사)


@dataclass
class VoiceFeatures:
    duration_sec: float
    f0_mean_hz: float | None
    f0_std_hz: float | None
    voiced_ratio: float
    rms_mean: float
    rms_std: float
    speaking_rate_sps: float | None  # 음절/초 추정치


def load_audio(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    return librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)


def extract_f0(y: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """pYIN 알고리즘으로 프레임별 F0(기본주파수)와 유성음 여부를 추출."""
    f0, voiced_flag, _voiced_prob = librosa.pyin(y, fmin=_PITCH_FMIN_HZ, fmax=_PITCH_FMAX_HZ, sr=sr)
    return f0, voiced_flag


def extract_rms(y: np.ndarray, hop_length: int = _HOP_LENGTH) -> np.ndarray:
    """프레임별 RMS 에너지."""
    return librosa.feature.rms(y=y, hop_length=hop_length)[0]


def estimate_speaking_rate(y: np.ndarray, sr: int, duration_sec: float, hop_length: int = _HOP_LENGTH) -> float | None:
    """발화 속도를 음절/초(syllables per second)로 추정.

    STT 없이는 단어 수를 셀 수 없어, onset strength(에너지 변화량) 곡선의 피크를
    음절 핵(syllable nuclei)으로 근사해서 세는 방식이다(de Jong & Wempe 2009 방식의
    단순화 버전). 배경 잡음이 크거나 발화가 뭉개진 경우 오차가 커질 수 있어 절대치보다
    baseline 대비 상대 비교용 지표로 쓸 것.
    """
    if duration_sec <= 0:
        return None

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    if onset_env.size == 0:
        return 0.0

    min_distance_frames = max(1, int(_MIN_SYLLABLE_INTERVAL_SEC * sr / hop_length))
    prominence = float(np.std(onset_env)) * 0.5
    peaks, _ = find_peaks(onset_env, distance=min_distance_frames, prominence=prominence)

    return len(peaks) / duration_sec


def extract_voice_features(audio_bytes: bytes) -> VoiceFeatures:
    y, sr = load_audio(audio_bytes)
    duration_sec = float(librosa.get_duration(y=y, sr=sr))

    if y.size == 0:
        return VoiceFeatures(
            duration_sec=duration_sec,
            f0_mean_hz=None,
            f0_std_hz=None,
            voiced_ratio=0.0,
            rms_mean=0.0,
            rms_std=0.0,
            speaking_rate_sps=None,
        )

    f0, voiced_flag = extract_f0(y, sr)
    voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
    f0_mean_hz = float(np.mean(voiced_f0)) if voiced_f0.size > 0 else None
    f0_std_hz = float(np.std(voiced_f0)) if voiced_f0.size > 0 else None
    voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None and voiced_flag.size > 0 else 0.0

    rms = extract_rms(y)
    rms_mean = float(np.mean(rms))
    rms_std = float(np.std(rms))

    speaking_rate_sps = estimate_speaking_rate(y, sr, duration_sec)

    return VoiceFeatures(
        duration_sec=duration_sec,
        f0_mean_hz=f0_mean_hz,
        f0_std_hz=f0_std_hz,
        voiced_ratio=voiced_ratio,
        rms_mean=rms_mean,
        rms_std=rms_std,
        speaking_rate_sps=speaking_rate_sps,
    )
