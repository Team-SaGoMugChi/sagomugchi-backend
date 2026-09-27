"""Validate the baseline contract required by diary emotion analysis."""

from datetime import datetime, timedelta
from math import isfinite
from typing import Mapping

from app.services.multimodal_contract import (
    FACE_STD_FIELDS,
    REQUIRED_FACE_MULTIMODAL_KEYS,
    REQUIRED_VOICE_MULTIMODAL_KEYS,
    VOICE_MEAN_FIELDS,
    VOICE_STD_FIELDS,
)


CURRENT_FEATURE_VERSION = 2
REQUIRED_VOICE_KEYS = {
    "pitchMean",
    "f0Std",
    "speechRate",
    "voicedRatio",
    "durationSec",
    "energyMean",
}
REQUIRED_FACE_KEYS = {
    "eyeAspectRatio",
    "mouthAspectRatio",
    "mouthWidthRatio",
    "eyebrowRaiseRatio",
}


class BaselineContractError(ValueError):
    """The saved reference cannot safely be used for a new analysis."""


def _finite_numbers(values: Mapping[str, object], required: set[str]) -> bool:
    for key in required:
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not isfinite(float(value)):
            return False
    return True


def validate_analysis_baseline(
    *,
    feature_version: int,
    measured_at: str,
    voice: Mapping[str, object],
    face: Mapping[str, object],
) -> None:
    if feature_version != CURRENT_FEATURE_VERSION:
        raise BaselineContractError("지원하지 않는 기준값 버전이에요. 다시 측정해주세요.")

    try:
        measured = datetime.fromisoformat(measured_at.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise BaselineContractError("기준값 측정 시각이 올바르지 않아요. 다시 측정해주세요.") from exc
    if measured.tzinfo is None or measured.utcoffset() != timedelta(0):
        raise BaselineContractError("기준값 측정 시각은 UTC여야 해요. 다시 측정해주세요.")

    required_voice = REQUIRED_VOICE_KEYS | REQUIRED_VOICE_MULTIMODAL_KEYS
    required_face = REQUIRED_FACE_KEYS | REQUIRED_FACE_MULTIMODAL_KEYS
    if not required_voice.issubset(voice) or not _finite_numbers(voice, required_voice):
        raise BaselineContractError("음성 기준값이 불완전해요. 다시 측정해주세요.")
    if not required_face.issubset(face) or not _finite_numbers(face, required_face):
        raise BaselineContractError("얼굴 기준값이 불완전해요. 다시 측정해주세요.")

    if (
        float(voice["pitchMean"]) <= 0
        or float(voice["f0Std"]) < 0
        or float(voice["speechRate"]) < 0
        or not 0 < float(voice["voicedRatio"]) <= 1
        or float(voice["durationSec"]) <= 0
        or float(voice["energyMean"]) <= 0
        or float(voice["windowCount"]) <= 0
        or float(voice["windowUsedCount"]) <= 0
        or float(voice["windowUsedCount"]) > float(voice["windowCount"])
        or float(voice["windowCount"]) != int(float(voice["windowCount"]))
        or float(voice["windowUsedCount"]) != int(float(voice["windowUsedCount"]))
        or float(voice[VOICE_MEAN_FIELDS["pitchMean"]]) <= 0
        or float(voice[VOICE_MEAN_FIELDS["energyMean"]]) <= 0
        or float(voice[VOICE_MEAN_FIELDS["speechRate"]]) < 0
        or any(float(voice[field]) < 0 for field in VOICE_STD_FIELDS.values())
    ):
        raise BaselineContractError("음성 기준값의 범위가 올바르지 않아요. 다시 측정해주세요.")
    if (
        any(float(face[key]) < 0 for key in REQUIRED_FACE_KEYS)
        or float(face["auFrameCount"]) <= 0
        or float(face["auTotalFrames"]) <= 0
        or float(face["auFrameCount"]) > float(face["auTotalFrames"])
        or float(face["auFrameCount"]) != int(float(face["auFrameCount"]))
        or float(face["auTotalFrames"]) != int(float(face["auTotalFrames"]))
        or any(float(face[field]) < 0 for field in FACE_STD_FIELDS.values())
    ):
        raise BaselineContractError("얼굴 기준값의 범위가 올바르지 않아요. 다시 측정해주세요.")
