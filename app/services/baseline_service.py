"""Validate baseline inputs before they can replace a saved reference."""

import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from math import isfinite

import cv2
import soundfile as sf

from app.models.baseline import BaselineProfile
from app.services.face_au import FaceAuUnavailable, get_face_au_extractor
from app.services.face_features import extract_face_features
from app.services.feature_maps import face_features_to_map, voice_features_to_map
from app.services.multimodal_contract import face_summary_to_map, voice_summary_to_map
from app.services.modality_emotion import face_log_summary
from app.services.voice_features import extract_voice_features
from app.services.voice_windows import VOICE_WINDOW_KEYS, analyze_windows, summarize_windows

logger = logging.getLogger(__name__)


class BaselineMeasurementError(ValueError):
    """A recoverable recording/capture failure; the user should measure again."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def build_baseline_profile(
    user_id: str,
    voice_bytes: bytes,
    face_image_bytes: bytes | Sequence[bytes],
) -> BaselineProfile:
    face_frames = (
        [face_image_bytes]
        if isinstance(face_image_bytes, bytes)
        else [frame for frame in face_image_bytes if frame]
    )
    if not voice_bytes:
        raise BaselineMeasurementError("invalid_audio", "음성 파일이 비어 있어요. 다시 측정해주세요.")
    if not face_frames:
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
        voice_summary = summarize_windows(analyze_windows(voice_bytes))
    except (sf.LibsndfileError, ValueError, EOFError) as exc:
        raise BaselineMeasurementError(
            "invalid_audio", "음성 파일을 읽을 수 없어요. 다시 녹음해주세요."
        ) from exc
    if (
        voice_summary.used_count <= 0
        or set(voice_summary.mean) != set(VOICE_WINDOW_KEYS)
        or set(voice_summary.std) != set(VOICE_WINDOW_KEYS)
        or any(not isfinite(value) for value in (*voice_summary.mean.values(), *voice_summary.std.values()))
    ):
        raise BaselineMeasurementError(
            "voice_not_detected", "목소리를 충분히 확인하지 못했어요. 마이크를 확인하고 다시 말해주세요."
        )
    voice.update(voice_summary_to_map(voice_summary))

    # Geometry retains one representative frame for the v1-compatible fields.
    # A missed first capture must not invalidate usable later frames.
    face = {}
    readable_frame = False
    for frame in face_frames:
        try:
            candidate = face_features_to_map(extract_face_features(frame))
        except (cv2.error, ValueError):
            continue
        readable_frame = True
        if candidate and all(value is not None and isfinite(value) and value >= 0 for value in candidate.values()):
            face = candidate
            break
    if not readable_frame:
        raise BaselineMeasurementError(
            "invalid_face_image", "얼굴 사진을 읽을 수 없어요. 다시 촬영해주세요."
        )
    if not face:
        raise BaselineMeasurementError(
            "face_not_detected", "얼굴을 확인하지 못했어요. 밝은 곳에서 얼굴을 화면 중앙에 맞춰 다시 측정해주세요."
        )

    try:
        extractor = get_face_au_extractor()
        face_aus = [extractor.extract(frame) for frame in face_frames]
    except FaceAuUnavailable as exc:
        logger.exception("Face AU extraction failed")
        raise BaselineMeasurementError(
            "face_analysis_unavailable", "표정 분석기를 준비하지 못했어요. 잠시 후 다시 측정해주세요."
        ) from exc
    if not any(frame.detected for frame in face_aus):
        raise BaselineMeasurementError(
            "face_not_detected", "얼굴을 확인하지 못했어요. 밝은 곳에서 얼굴을 화면 중앙에 맞춰 다시 측정해주세요."
        )
    face.update(face_summary_to_map(face_log_summary(face_aus)))

    return BaselineProfile(
        feature_version=2,
        user_id=user_id,
        voice=voice,
        face=face,
        measured_at=datetime.now(timezone.utc).isoformat(),
    )
