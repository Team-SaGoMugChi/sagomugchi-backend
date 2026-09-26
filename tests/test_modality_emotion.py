import math

import pytest

from app.services.face_au import AU_KEYS, FaceAu, FaceAuSummary
from app.services.modality_emotion import (
    FACE_PROTOTYPES,
    FACE_STD_FLOOR,
    describe_signals,
    face_emotion,
    face_emotion_from_frames,
    face_log_summary,
    face_timeline,
    face_z,
    log_au,
    voice_arousal,
    voice_arousal_from_summary,
    voice_timeline,
    voice_z,
)
from app.services.text_emotion import EMOTION_LABELS
from app.services.voice_windows import VoiceWindow, VoiceWindowSummary


def _au(value: float, **overrides: float) -> dict[str, float]:
    return {key: overrides.get(key, value) for key in AU_KEYS}


def _neutral_baseline() -> FaceAuSummary:
    # 무표정: 모든 AU가 0 근처에서 거의 안 움직인다
    return face_log_summary([FaceAu(True, _au(0.0))] * 10)


def test_prototypes_cover_the_six_team_emotions():
    assert set(FACE_PROTOTYPES) == set(EMOTION_LABELS)
    assert all(set(aus) <= set(AU_KEYS) for aus in FACE_PROTOTYPES.values())


def test_log_scale_makes_a_slight_smile_visible():
    # 살짝 미소(0.002)도 무표정(0) 대비 뚜렷한 z가 나온다 — 선형이면 0.002 / 0.02 = 0.1
    baseline = _neutral_baseline()
    z = face_z(log_au(_au(0.0, au12=0.002)), baseline)

    assert z["au12"] == pytest.approx((math.log10(0.003) - math.log10(0.001)) / FACE_STD_FLOOR)
    assert z["au12"] > 2
    assert z["au4"] == pytest.approx(0.0)


def test_smile_reads_as_joy_with_positive_valence():
    emotion = face_emotion_from_frames([FaceAu(True, _au(0.0, au6=0.3, au12=0.6))] * 3, _neutral_baseline())

    assert max(emotion.scores, key=emotion.scores.get) == "기쁨"
    assert emotion.valence > 0.5


def test_sad_mouth_reads_as_sadness_and_hurt_equally():
    emotion = face_emotion_from_frames(
        [FaceAu(True, _au(0.0, au4=0.05, au15=0.05, au17=0.1))] * 3, _neutral_baseline()
    )

    ranked = sorted(emotion.scores, key=emotion.scores.get, reverse=True)
    assert set(ranked[:2]) == {"슬픔", "상처"}  # 얼굴로는 둘을 가르지 않는다
    assert emotion.scores["슬픔"] == emotion.scores["상처"]
    assert emotion.valence < -0.5


def test_aus_dropping_below_baseline_are_not_evidence():
    baseline = face_log_summary([FaceAu(True, _au(0.3))] * 10)
    emotion = face_emotion(face_z(log_au(_au(0.0)), baseline))

    assert all(score == 0 for score in emotion.scores.values())
    assert emotion.valence == 0


def test_no_face_or_no_baseline_gives_no_face_emotion():
    empty = FaceAuSummary(frame_count=0, total_frames=3, mean={}, std={})

    assert face_emotion_from_frames([FaceAu(False, {})] * 3, _neutral_baseline()) is None
    assert face_emotion_from_frames([FaceAu(True, _au(0.1))], empty) is None


def test_face_timeline_keeps_missing_frames_as_gaps():
    moments = face_timeline(
        [(0.0, FaceAu(True, _au(0.0, au12=0.5))), (1.0, FaceAu(False, {}))], _neutral_baseline()
    )

    assert [m.time_sec for m in moments] == [0.0, 1.0]
    assert moments[0].emotion.valence > 0
    assert moments[1].emotion is None


_VOICE_BASELINE = VoiceWindowSummary(
    window_count=10,
    used_count=10,
    mean={"pitchMean": 200.0, "energyMean": 0.05, "speechRate": 4.0},
    std={"pitchMean": 10.0, "energyMean": 0.01, "speechRate": 0.5},
)


def test_voice_z_uses_window_std():
    z = voice_z({"pitchMean": 220.0, "energyMean": 0.05, "speechRate": 3.0}, _VOICE_BASELINE)

    assert z == pytest.approx({"pitchMean": 2.0, "energyMean": 0.0, "speechRate": -2.0})


def test_voice_std_floor_stops_tiny_baselines_from_exaggerating():
    baseline = VoiceWindowSummary(1, 1, mean={"pitchMean": 200.0}, std={"pitchMean": 0.1})

    # σ 0.1Hz 그대로면 z=50. 평균의 5%(10Hz)로 올려 z=0.5
    assert voice_z({"pitchMean": 205.0}, baseline)["pitchMean"] == pytest.approx(0.5)


def test_arousal_is_weighted_and_bounded():
    high = voice_arousal({"pitchMean": 10.0, "speechRate": 10.0, "energyMean": 10.0})
    mixed = voice_arousal({"pitchMean": 3.0, "speechRate": -3.0})
    energy_only = voice_arousal({"energyMean": -3.0})

    assert high.arousal == pytest.approx(1.0)  # z는 ±3에서 자른다
    assert mixed.arousal == pytest.approx(0.0)
    assert energy_only.arousal == pytest.approx(-1.0)
    assert voice_arousal({}) is None


def test_lower_and_slower_voice_is_low_arousal():
    today = VoiceWindowSummary(5, 5, mean={"pitchMean": 180.0, "energyMean": 0.04, "speechRate": 3.0}, std={})

    assert voice_arousal_from_summary(today, _VOICE_BASELINE).arousal < -0.5


def test_voice_timeline_marks_silent_windows():
    windows = [
        VoiceWindow(0.0, 3.0, voiced_ratio=0.8, pitch_mean=230.0, energy_mean=0.07, speech_rate=5.0),
        VoiceWindow(3.0, 3.0, voiced_ratio=0.05, pitch_mean=None, energy_mean=0.001, speech_rate=0.0),
    ]

    moments = voice_timeline(windows, _VOICE_BASELINE)

    assert moments[0].arousal.arousal > 0.5
    assert moments[1].arousal is None


def test_signals_describe_only_clear_changes_biggest_first():
    signals = describe_signals(
        face={"au15": 6.0, "au4": 2.5, "au12": 1.0},
        voice={"pitchMean": -3.0, "speechRate": 0.5},
    )

    assert signals == ["입꼬리가 평소보다 처짐", "목소리 높이가 평소보다 낮음", "미간을 평소보다 찌푸림"]


def test_signals_are_limited_and_tolerate_missing_modalities():
    face = {"au12": 9.0, "au6": 8.0, "au4": 7.0, "au15": 6.0, "au17": 5.0}

    assert len(describe_signals(face, None, limit=2)) == 2
    assert describe_signals(None, None) == []
