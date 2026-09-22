"""Validate baseline inputs before they can replace a saved reference."""

from datetime import datetime, timezone
from math import isfinite

import cv2
import soundfile as sf

from app.models.baseline import BaselineProfile
from app.services.face_features import extract_face_features
from app.services.feature_maps import face_features_to_map, voice_features_to_map
from app.services.voice_features import extract_voice_features


class BaselineMeasurementError(ValueError):
    """A recoverable recording/capture failure; the user should measure again."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def build_baseline_profile(user_id: str, voice_bytes: bytes, face_image_bytes: bytes) -> BaselineProfile:
    if not voice_bytes:
        raise BaselineMeasurementError("invalid_audio", "음성 파일이 비어 있어요. 다시 측정해주세요.")
    if not face_image_bytes:
        raise BaselineMeasurementError("invalid_face_image", "얼굴 사진이 비어 있어요. 다시 측정해주세요.")

    try:
        voice_features = extract_voice_features(voice_bytes)
    except (sf.LibsndfileError, ValueError, EOFError) as exc:
        raise BaselineMeasurementError(
            "invalid_audio", "음성 파일을 읽을 수 없어요. 다시 녹음해주세요."
        ) from exc

    voice = voice_features_to_map(voice_features)
    # Handoff metadata is deliberately baseline-only: adding these keys to the
    # shared feature map would silently change the existing fusion formula.
    voice.update({
        "voicedRatio": voice_features.voiced_ratio,
        "durationSec": voice_features.duration_sec,
    })
    if voice_features.f0_std_hz is not None:
        voice["f0Std"] = voice_features.f0_std_hz
    # No clinical quality threshold: reject only missing/non-finite measurements
    # and recordings without a measurable voiced signal.
    if (
        not isfinite(voice_features.duration_sec)
        or voice_features.duration_sec <= 0
        or not isfinite(voice_features.voiced_ratio)
        or not 0 < voice_features.voiced_ratio <= 1
        or voice_features.f0_std_hz is None
        or voice_features.f0_std_hz < 0
        or voice.get("pitchMean", 0) <= 0
        or voice.get("energyMean", 0) <= 0
        or any(not isfinite(value) for value in voice.values())
    ):
        raise BaselineMeasurementError(
            "voice_not_detected", "목소리를 충분히 확인하지 못했어요. 마이크를 확인하고 다시 말해주세요."
        )

    try:
        face_features = extract_face_features(face_image_bytes)
    except (cv2.error, ValueError) as exc:
        raise BaselineMeasurementError(
            "invalid_face_image", "얼굴 사진을 읽을 수 없어요. 다시 촬영해주세요."
        ) from exc

    face = face_features_to_map(face_features)
    if not face or any(value is None or not isfinite(value) or value < 0 for value in face.values()):
        raise BaselineMeasurementError(
            "face_not_detected", "얼굴을 확인하지 못했어요. 밝은 곳에서 얼굴을 화면 중앙에 맞춰 다시 측정해주세요."
        )

    return BaselineProfile(
        user_id=user_id,
        voice=voice,
        face=face,
        measured_at=datetime.now(timezone.utc).isoformat(),
    )
