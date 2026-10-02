"""Flat baseline fields used by the multimodal emotion pipeline.

Firestore keeps ``voice`` and ``face`` as flat numeric maps so the Flutter
client can forward them without interpreting the model.  This module owns the
mapping between those transport fields and the statistical summaries used by
the fusion services.
"""

from collections.abc import Mapping
from math import isfinite

from app.services.face_au import AU_KEYS, FaceAuSummary
from app.services.voice_windows import VOICE_WINDOW_KEYS, VoiceWindowSummary


VOICE_MEAN_FIELDS = {
    "pitchMean": "windowPitchMean",
    "energyMean": "windowEnergyMean",
    "speechRate": "windowSpeechRate",
}
VOICE_STD_FIELDS = {
    "pitchMean": "windowPitchStd",
    "energyMean": "windowEnergyStd",
    "speechRate": "windowSpeechRateStd",
}
FACE_MEAN_FIELDS = {key: f"{key}LogMean" for key in AU_KEYS}
FACE_STD_FIELDS = {key: f"{key}LogStd" for key in AU_KEYS}

REQUIRED_VOICE_MULTIMODAL_KEYS = {
    *VOICE_MEAN_FIELDS.values(),
    *VOICE_STD_FIELDS.values(),
    "windowCount",
    "windowUsedCount",
}
REQUIRED_FACE_MULTIMODAL_KEYS = {
    *FACE_MEAN_FIELDS.values(),
    *FACE_STD_FIELDS.values(),
    "auFrameCount",
    "auTotalFrames",
}


def voice_summary_to_map(summary: VoiceWindowSummary) -> dict[str, float]:
    return {
        **{field: summary.mean[key] for key, field in VOICE_MEAN_FIELDS.items()},
        **{field: summary.std[key] for key, field in VOICE_STD_FIELDS.items()},
        "windowCount": float(summary.window_count),
        "windowUsedCount": float(summary.used_count),
    }


def voice_summary_from_map(values: Mapping[str, float]) -> VoiceWindowSummary:
    return VoiceWindowSummary(
        window_count=int(values["windowCount"]),
        used_count=int(values["windowUsedCount"]),
        mean={key: float(values[field]) for key, field in VOICE_MEAN_FIELDS.items()},
        std={key: float(values[field]) for key, field in VOICE_STD_FIELDS.items()},
    )


def face_summary_to_map(summary: FaceAuSummary) -> dict[str, float]:
    return {
        **{field: summary.mean[key] for key, field in FACE_MEAN_FIELDS.items()},
        **{field: summary.std[key] for key, field in FACE_STD_FIELDS.items()},
        "auFrameCount": float(summary.frame_count),
        "auTotalFrames": float(summary.total_frames),
    }


def face_summary_from_map(values: Mapping[str, float]) -> FaceAuSummary:
    return FaceAuSummary(
        frame_count=int(values["auFrameCount"]),
        total_frames=int(values["auTotalFrames"]),
        mean={key: float(values[field]) for key, field in FACE_MEAN_FIELDS.items()},
        std={key: float(values[field]) for key, field in FACE_STD_FIELDS.items()},
    )


def group_face_summary_from_map(values: Mapping[str, float], group: str) -> FaceAuSummary | None:
    """Optional speaking/silent baseline; older v2 documents use the overall one."""
    if group not in {"speaking", "silent"}:
        raise ValueError("invalid face group")
    count = values.get(f"{group}FrameCount", 0)
    if (
        isinstance(count, bool)
        or not isinstance(count, (int, float))
        or not isfinite(count)
        or count <= 0
        or count != int(count)
    ):
        return None
    fields = {
        key: values.get(f"{group}{field[0].upper()}{field[1:]}")
        for key, field in FACE_MEAN_FIELDS.items()
    }
    std = {
        key: values.get(f"{group}{field[0].upper()}{field[1:]}")
        for key, field in FACE_STD_FIELDS.items()
    }
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        for value in (*fields.values(), *std.values())
    ) or any(value < 0 for value in std.values()):
        return None
    return FaceAuSummary(
        frame_count=int(count), total_frames=int(count),
        mean={key: float(value) for key, value in fields.items()},
        std={key: float(value) for key, value in std.items()},
    )
