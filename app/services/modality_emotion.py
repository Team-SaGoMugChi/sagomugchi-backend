"""표정 AU·음성 구간 특징을 baseline과 비교해 감정 근거를 뽑는다 — fusion의 입력.

논문 식 (1)처럼 절대값이 아니라 baseline 대비 z-score, (현재 − μ_baseline) / σ_baseline로
본다. 사람마다 기본 얼굴·목소리가 달라서, "얼마나 움직여야 감정인가"는 이 비교가 사람마다
맞춰 준다. 여기서 정하는 건 "어떤 움직임을 볼 것인가"뿐이고, 그 근거는 특정 사람의 데이터가
아니라 이론(에크만 EMFACS, 감정 원형 모델)이다.

표정
    blendshape는 작은 표정에서 0 근처에 머물러(살짝 미소 0.002, 활짝 웃음 0.65) 선형으로
    비교하면 작은 변화가 묻힌다. log10(x + LOG_EPS)로 바꾼 뒤 z-score를 낸다.
    AU가 평소보다 "올라간" 만큼만 감정 근거로 친다 — 내려간 건 그 감정이 없다는 뜻이지
    다른 감정의 근거가 아니다. 슬픔과 상처는 얼굴로 구분할 수 없어(같은 AU 조합) 같은 값을
    준다. 둘을 가르는 건 텍스트다.

음성
    목소리만으로 분노와 기쁨 같은 감정 종류를 가르는 건 어렵다. 그래서 흥분도(각성도,
    arousal)까지만 뽑는다. 에너지는 마이크·거리에 따라 세션마다 달라져서(BASELINE_HANDOFF.md)
    가중치를 절반으로 둔다.

이 모듈의 가중치·문턱값은 학습된 값이 아니라 이론 기반 잠정 규칙이다. 오또 일기로 만든
평가셋으로 검증해야 한다.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from app.services.face_au import AU_KEYS, FaceAu, FaceAuSummary, summarize_frames
from app.services.voice_windows import (
    MIN_VOICED_RATIO,
    VOICE_WINDOW_KEYS,
    VoiceWindow,
    VoiceWindowSummary,
)

LOG_EPS = 1e-3
# 무표정의 흔들림이 거의 0이라 그대로 나누면 z가 무한대로 튄다. log10 기준 0.1 ≈ 26% 변화.
FACE_STD_FLOOR = 0.1
# 이 이상 올라간 AU는 "뚜렷하다"로 보고 더 키우지 않는다(활짝 웃음은 z가 +28까지 나온다).
FACE_Z_CAP = 5.0

# 에크만 EMFACS의 감정별 AU 조합을 우리 6종에 맞춘 것.
FACE_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "기쁨": ("au6", "au12"),
    "슬픔": ("au1", "au4", "au15", "au17"),
    "상처": ("au1", "au4", "au15", "au17"),
    "분노": ("au4", "au5", "au7"),
    "불안": ("au1", "au2", "au4", "au5"),
    "당황": ("au1", "au2", "au5"),
}
_POSITIVE_AUS = ("au6", "au12")
_NEGATIVE_AUS = ("au4", "au15", "au17")

# σ가 평균의 이 비율보다 작으면 이 값으로 둔다 — 짧은 baseline에서 σ가 우연히 작게 나와
# 작은 변화가 과장되는 것을 막는다.
VOICE_STD_FLOOR_RATIO = 0.05
VOICE_Z_CAP = 3.0
VOICE_WEIGHTS = {"pitchMean": 1.0, "speechRate": 1.0, "energyMean": 0.5}

FACE_SIGNAL_Z = 2.0
VOICE_SIGNAL_Z = 1.5


@dataclass
class FaceEmotion:
    scores: dict[str, float]  # 감정별 근거 0~1 (텍스트 6종과 같은 키)
    valence: float  # 표정 긍정도 −1~1
    z: dict[str, float]  # AU별 z-score


@dataclass
class VoiceArousal:
    arousal: float  # 흥분도 −1(가라앉음)~1(흥분·긴장)
    z: dict[str, float]  # 특징별 z-score


@dataclass
class FaceMoment:
    time_sec: float
    emotion: FaceEmotion | None  # 얼굴을 못 찾은 프레임은 None


@dataclass
class VoiceMoment:
    start_sec: float
    arousal: VoiceArousal | None  # 말하지 않은 구간은 None


def log_au(au: Mapping[str, float]) -> dict[str, float]:
    return {key: math.log10(value + LOG_EPS) for key, value in au.items()}


def face_log_summary(frames: Sequence[FaceAu]) -> FaceAuSummary:
    """프레임들의 AU를 로그 스케일로 바꿔 평균·표준편차를 낸다(baseline과 일기가 같이 쓴다)."""
    return summarize_frames([FaceAu(f.detected, log_au(f.au) if f.detected else {}) for f in frames])


def face_z(current_log: Mapping[str, float], baseline_log: FaceAuSummary) -> dict[str, float]:
    """로그 스케일 AU 값 → baseline 대비 z. 양쪽에 다 있는 AU만 계산한다."""
    return {
        key: (current_log[key] - baseline_log.mean[key]) / max(baseline_log.std.get(key, 0.0), FACE_STD_FLOOR)
        for key in AU_KEYS
        if key in current_log and key in baseline_log.mean
    }


def _activation(z: Mapping[str, float], key: str) -> float:
    return min(max(z.get(key, 0.0), 0.0), FACE_Z_CAP) / FACE_Z_CAP


def face_emotion(z: Mapping[str, float]) -> FaceEmotion:
    scores = {
        label: float(np.mean([_activation(z, au) for au in aus]))
        for label, aus in FACE_PROTOTYPES.items()
    }
    valence = float(np.mean([_activation(z, au) for au in _POSITIVE_AUS])) - float(
        np.mean([_activation(z, au) for au in _NEGATIVE_AUS])
    )
    return FaceEmotion(scores=scores, valence=valence, z=dict(z))


def face_emotion_from_frames(frames: Sequence[FaceAu], baseline_log: FaceAuSummary) -> FaceEmotion | None:
    """일기 전체의 표정 감정 — 오늘 프레임들의 로그 평균을 baseline과 비교한다."""
    today = face_log_summary(frames)
    if today.frame_count == 0 or baseline_log.frame_count == 0:
        return None
    return face_emotion(face_z(today.mean, baseline_log))


def face_timeline(
    frames: Sequence[tuple[float, FaceAu]], baseline_log: FaceAuSummary
) -> list[FaceMoment]:
    """(촬영 시각, 프레임) 목록 → 프레임별 표정 감정. 영상 장면 분할·실시간 표시용."""
    return [
        FaceMoment(t, face_emotion(face_z(log_au(frame.au), baseline_log)) if frame.detected else None)
        for t, frame in frames
    ]


def voice_z(current: Mapping[str, float], baseline: VoiceWindowSummary) -> dict[str, float]:
    result = {}
    for key in VOICE_WINDOW_KEYS:
        if key not in current or key not in baseline.mean:
            continue
        mean = baseline.mean[key]
        std = max(baseline.std.get(key, 0.0), abs(mean) * VOICE_STD_FLOOR_RATIO)
        if std > 0:
            result[key] = (current[key] - mean) / std
    return result


def voice_arousal(z: Mapping[str, float]) -> VoiceArousal | None:
    weighted = [
        (min(max(z[key], -VOICE_Z_CAP), VOICE_Z_CAP) / VOICE_Z_CAP, weight)
        for key, weight in VOICE_WEIGHTS.items()
        if key in z
    ]
    if not weighted:
        return None
    arousal = sum(value * weight for value, weight in weighted) / sum(weight for _, weight in weighted)
    return VoiceArousal(arousal=arousal, z=dict(z))


def voice_arousal_from_summary(today: VoiceWindowSummary, baseline: VoiceWindowSummary) -> VoiceArousal | None:
    """일기 전체의 흥분도 — 오늘 말한 구간들의 평균을 baseline과 비교한다."""
    return voice_arousal(voice_z(today.mean, baseline))


def voice_timeline(windows: Sequence[VoiceWindow], baseline: VoiceWindowSummary) -> list[VoiceMoment]:
    moments = []
    for window in windows:
        if window.voiced_ratio < MIN_VOICED_RATIO:
            moments.append(VoiceMoment(window.start_sec, None))
            continue
        current = {"energyMean": window.energy_mean}
        if window.pitch_mean is not None:
            current["pitchMean"] = window.pitch_mean
        if window.speech_rate is not None:
            current["speechRate"] = window.speech_rate
        moments.append(VoiceMoment(window.start_sec, voice_arousal(voice_z(current, baseline))))
    return moments


# (키, 방향) → 문장. 방향 +1은 평소보다 올라감, −1은 내려감.
_FACE_SIGNALS = {
    ("au12", 1): "평소보다 많이 웃음",
    ("au6", 1): "볼이 올라갈 만큼 웃음",
    ("au4", 1): "미간을 평소보다 찌푸림",
    ("au15", 1): "입꼬리가 평소보다 처짐",
    ("au17", 1): "턱에 힘이 들어감(울먹이는 표정)",
    ("au1", 1): "눈썹 안쪽이 평소보다 올라감(걱정하는 표정)",
    ("au5", 1): "눈을 평소보다 크게 뜸",
}
_VOICE_SIGNALS = {
    ("pitchMean", 1): "목소리 높이가 평소보다 높음",
    ("pitchMean", -1): "목소리 높이가 평소보다 낮음",
    ("speechRate", 1): "말 속도가 평소보다 빠름",
    ("speechRate", -1): "말 속도가 평소보다 느림",
    ("energyMean", 1): "목소리가 평소보다 큼",
    ("energyMean", -1): "목소리가 평소보다 작음",
}


def describe_signals(
    face: Mapping[str, float] | None,
    voice: Mapping[str, float] | None,
    limit: int = 4,
) -> list[str]:
    """baseline 대비 뚜렷한 변화를 사람이 읽을 문장으로 — 상담봇 맥락(signals)용. 큰 변화 순."""
    found: list[tuple[float, str]] = []
    for source, table, threshold in ((face, _FACE_SIGNALS, FACE_SIGNAL_Z), (voice, _VOICE_SIGNALS, VOICE_SIGNAL_Z)):
        for key, z in (source or {}).items():
            if abs(z) < threshold:
                continue
            sentence = table.get((key, 1 if z > 0 else -1))
            if sentence:
                found.append((abs(z) / threshold, sentence))
    found.sort(key=lambda item: item[0], reverse=True)
    return [sentence for _, sentence in found[:limit]]
