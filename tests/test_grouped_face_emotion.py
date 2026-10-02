from types import SimpleNamespace

import numpy as np
import pytest

from app.services import analysis_media
from app.services.face_au import AU_KEYS, FaceAu
from app.services.modality_emotion import face_emotion_from_grouped_frames, face_log_summary
from app.services.multimodal_contract import group_face_summary_from_map, face_summary_to_map, voice_summary_to_map
from app.services.voice_features import VoiceFeatures
from app.services.voice_windows import VoiceWindowSummary


def _frame(smile: float) -> FaceAu:
    return FaceAu(True, {key: smile if key in {"au6", "au12"} else 0.0 for key in AU_KEYS})


def test_daily_frame_uses_matching_speech_baseline():
    neutral = face_log_summary([_frame(0.0)] * 3)
    speaking = face_log_summary([_frame(0.5)] * 3)
    current = [_frame(0.5), _frame(0.0)]

    matched = face_emotion_from_grouped_frames(current, [speaking, neutral])
    mismatched = face_emotion_from_grouped_frames(current, [neutral, speaking])

    assert matched.valence == pytest.approx(0)
    assert mismatched.valence > 0


def test_group_baseline_is_optional_for_legacy_v2_profile():
    baseline = face_log_summary([_frame(0.0)] * 3)
    values = face_summary_to_map(baseline)
    assert group_face_summary_from_map(values, "speaking") is None
    values["speakingFrameCount"] = 3.0
    for key, value in face_summary_to_map(baseline).items():
        if key.endswith(("LogMean", "LogStd")):
            values["speaking" + key[0].upper() + key[1:]] = value
    assert group_face_summary_from_map(values, "speaking") == baseline


def test_diary_timeline_selects_speaking_and_silent_groups(monkeypatch):
    neutral = face_log_summary([_frame(0.0)] * 3)
    speaking = face_log_summary([_frame(0.5)] * 3)
    face_map = face_summary_to_map(neutral)
    face_map["speakingFrameCount"] = 3.0
    face_map["silentFrameCount"] = 3.0
    for group, summary in (("speaking", speaking), ("silent", neutral)):
        for key, value in face_summary_to_map(summary).items():
            if key.endswith(("LogMean", "LogStd")):
                face_map[group + key[0].upper() + key[1:]] = value

    window = VoiceWindowSummary(
        window_count=1, used_count=1,
        mean={"pitchMean": 200.0, "energyMean": 0.1, "speechRate": 4.0},
        std={"pitchMean": 10.0, "energyMean": 0.01, "speechRate": 0.5},
    )
    monkeypatch.setattr(analysis_media, "analyze_windows", lambda _: [])
    monkeypatch.setattr(analysis_media, "summarize_windows", lambda _: window)
    monkeypatch.setattr(
        analysis_media, "get_face_au_extractor",
        lambda: SimpleNamespace(extract=lambda image: _frame(0.5 if image == b"speaking" else 0.0)),
    )
    features = VoiceFeatures(
        duration_sec=2.0, f0_mean_hz=200.0, f0_std_hz=0.0,
        voiced_ratio=0.5, rms_mean=0.1, rms_std=0.0, speaking_rate_sps=4.0,
        voiced_flags=np.array([True, True, False, False]), voiced_hop_sec=0.5,
    )
    result = analysis_media.extract_daily_multimodal_features(
        b"voice", [b"speaking", b"silent"], voice_summary_to_map(window), face_map,
        face_timeline="0,0;1500,0", voice_features=features,
    )
    assert result.face.valence == pytest.approx(0)

    with pytest.raises(analysis_media.AnalysisMediaError) as error:
        analysis_media.extract_daily_multimodal_features(
            b"voice", [b"speaking", b"silent"], voice_summary_to_map(window), face_map,
            face_timeline="1500,0;0,0", voice_features=features,
        )
    assert error.value.code == "invalid_face_timeline"
