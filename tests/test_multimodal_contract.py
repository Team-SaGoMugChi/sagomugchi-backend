from app.services.face_au import FaceAuSummary
from app.services.multimodal_contract import (
    face_summary_from_map,
    face_summary_to_map,
    voice_summary_from_map,
    voice_summary_to_map,
)
from app.services.voice_windows import VoiceWindowSummary


def test_voice_summary_round_trip_preserves_v2_statistics():
    summary = VoiceWindowSummary(
        window_count=4,
        used_count=3,
        mean={"pitchMean": 210.0, "energyMean": 0.2, "speechRate": 4.5},
        std={"pitchMean": 10.0, "energyMean": 0.03, "speechRate": 0.5},
    )

    assert voice_summary_from_map(voice_summary_to_map(summary)) == summary


def test_face_summary_round_trip_preserves_log_au_statistics():
    keys = ("au1", "au2", "au4", "au5", "au6", "au7", "au12", "au15", "au17")
    summary = FaceAuSummary(
        frame_count=1,
        total_frames=1,
        mean={key: -2.0 for key in keys},
        std={key: 0.0 for key in keys},
    )

    assert face_summary_from_map(face_summary_to_map(summary)) == summary
