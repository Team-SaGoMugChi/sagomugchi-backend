"""Validate diary media before baseline comparison and emotion fusion."""

from math import isfinite
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import cv2
import soundfile as sf

from app.services.face_features import FaceFeatures, extract_face_features
from app.services.face_au import FaceAuUnavailable, get_face_au_extractor
from app.services.feature_maps import face_features_to_map, voice_features_to_map
from app.services.modality_emotion import (
    FaceEmotion,
    VoiceArousal,
    face_emotion_from_frames,
    voice_arousal_from_summary,
)
from app.services.multimodal_contract import face_summary_from_map, voice_summary_from_map
from app.services.voice_features import VoiceFeatures, extract_voice_features
from app.services.voice_windows import VOICE_WINDOW_KEYS, analyze_windows, summarize_windows


class AnalysisMediaError(ValueError):
    """A recoverable daily recording/capture failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AnalysisMediaUnavailable(RuntimeError):
    """The server-side analysis model could not be loaded."""


@dataclass
class DailyMultimodalFeatures:
    face: FaceEmotion
    voice: VoiceArousal


def extract_analysis_features(
    voice_bytes: bytes,
    face_image_bytes: bytes | Sequence[bytes],
) -> tuple[VoiceFeatures, FaceFeatures]:
    face_frames = (
        [face_image_bytes]
        if isinstance(face_image_bytes, bytes)
        else [frame for frame in face_image_bytes if frame]
    )
    if not voice_bytes:
        raise AnalysisMediaError("invalid_audio", "음성 파일이 비어 있어요. 다시 녹음해주세요.")
    if not face_frames:
        raise AnalysisMediaError("invalid_face_image", "얼굴 사진이 비어 있어요. 다시 촬영해주세요.")

    try:
        voice_features = extract_voice_features(voice_bytes)
    except (sf.LibsndfileError, ValueError, EOFError) as exc:
        raise AnalysisMediaError(
            "invalid_audio", "음성 파일을 읽을 수 없어요. 다시 녹음해주세요."
        ) from exc

    voice = voice_features_to_map(voice_features)
    if (
        not isfinite(voice_features.duration_sec)
        or voice_features.duration_sec <= 0
        or not isfinite(voice_features.voiced_ratio)
        or not 0 < voice_features.voiced_ratio <= 1
        or voice.get("pitchMean", 0) <= 0
        or voice.get("energyMean", 0) <= 0
        or "speechRate" not in voice
        or any(not isfinite(value) for value in voice.values())
    ):
        raise AnalysisMediaError(
            "voice_not_detected",
            "목소리를 충분히 확인하지 못했어요. 마이크를 확인하고 다시 녹음해주세요.",
        )

    face_features = None
    readable_frame = False
    for frame in face_frames:
        try:
            candidate = extract_face_features(frame)
        except (cv2.error, ValueError):
            continue
        readable_frame = True
        face = face_features_to_map(candidate)
        if face and all(value is not None and isfinite(value) and value >= 0 for value in face.values()):
            face_features = candidate
            break
    if not readable_frame:
        raise AnalysisMediaError(
            "invalid_face_image", "얼굴 사진을 읽을 수 없어요. 다시 촬영해주세요."
        )
    if face_features is None:
        raise AnalysisMediaError(
            "face_not_detected",
            "얼굴을 확인하지 못했어요. 밝은 곳에서 얼굴을 화면 중앙에 맞춰 다시 촬영해주세요.",
        )

    return voice_features, face_features


def extract_daily_multimodal_features(
    voice_bytes: bytes,
    face_image_bytes: bytes | Sequence[bytes],
    baseline_voice: Mapping[str, float],
    baseline_face: Mapping[str, float],
) -> DailyMultimodalFeatures:
    """Extract v2 face/voice evidence using the saved statistical baseline."""
    try:
        current_voice = summarize_windows(analyze_windows(voice_bytes))
    except (sf.LibsndfileError, ValueError, EOFError) as exc:
        raise AnalysisMediaError(
            "invalid_audio", "음성 파일을 읽을 수 없어요. 다시 녹음해주세요."
        ) from exc
    if current_voice.used_count <= 0 or set(current_voice.mean) != set(VOICE_WINDOW_KEYS):
        raise AnalysisMediaError(
            "voice_not_detected",
            "목소리를 충분히 확인하지 못했어요. 마이크를 확인하고 다시 녹음해주세요.",
        )

    face_frames = (
        [face_image_bytes]
        if isinstance(face_image_bytes, bytes)
        else [frame for frame in face_image_bytes if frame]
    )
    if not face_frames:
        raise AnalysisMediaError(
            "invalid_face_image", "얼굴 사진이 비어 있어요. 다시 촬영해주세요."
        )
    try:
        extractor = get_face_au_extractor()
        current_faces = [extractor.extract(frame) for frame in face_frames]
    except FaceAuUnavailable as exc:
        raise AnalysisMediaUnavailable("Face emotion model is unavailable") from exc
    if not any(frame.detected for frame in current_faces):
        raise AnalysisMediaError(
            "face_not_detected",
            "얼굴을 확인하지 못했어요. 밝은 곳에서 얼굴을 화면 중앙에 맞춰 다시 촬영해주세요.",
        )

    voice = voice_arousal_from_summary(
        current_voice, voice_summary_from_map(baseline_voice)
    )
    face = face_emotion_from_frames(
        current_faces, face_summary_from_map(baseline_face)
    )
    if voice is None:
        raise AnalysisMediaError(
            "voice_not_detected",
            "목소리 특징을 계산하지 못했어요. 다시 녹음해주세요.",
        )
    if face is None:
        raise AnalysisMediaError(
            "face_not_detected",
            "표정 특징을 계산하지 못했어요. 다시 촬영해주세요.",
        )
    return DailyMultimodalFeatures(face=face, voice=voice)
