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
from app.services.voice_windows import MIN_VOICED_RATIO, VOICE_WINDOW_KEYS, analyze_windows, summarize_windows

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
    face_timeline: str | None = None,
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
        voice_windows = analyze_windows(voice_bytes)
        voice_summary = summarize_windows(voice_windows)
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

    # Old single-frame clients have no synchronized timeline. New clients send
    # one recording-relative timestamp and prompt flag per uploaded image.
    timeline: list[tuple[float, bool]] = []
    if face_timeline is not None:
        try:
            entries = face_timeline.split(";")
            if len(entries) != len(face_frames):
                raise ValueError("frame count mismatch")
            for entry in entries:
                timestamp, prompt = entry.split(",")
                timestamp_ms = int(timestamp)
                if timestamp_ms < 0 or timestamp_ms > voice_features.duration_sec * 1000 + 1000 or prompt not in {"0", "1"}:
                    raise ValueError("invalid frame time")
                timeline.append((timestamp_ms / 1000, prompt == "1"))
            if any(later[0] < earlier[0] for earlier, later in zip(timeline, timeline[1:])):
                raise ValueError("out of order")
        except ValueError as exc:
            raise BaselineMeasurementError("invalid_face_timeline", "얼굴 촬영 시각이 올바르지 않아요. 다시 측정해주세요.") from exc

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
    if timeline:
        speaking_frames = []
        silent_frames = []
        for frame, (timestamp_sec, prompt_speaking) in zip(face_aus, timeline):
            if prompt_speaking:
                continue  # TTS is audible in the microphone but is not user speech.
            window = next((w for w in voice_windows if w.start_sec <= timestamp_sec < w.start_sec + w.duration_sec), None)
            if window is None:
                continue
            voiced = window.voiced_ratio >= MIN_VOICED_RATIO
            if voice_features.voiced_flags is not None and voice_features.voiced_hop_sec:
                hop = voice_features.voiced_hop_sec
                start = max(0, int((timestamp_sec - 0.25) / hop))
                end = min(len(voice_features.voiced_flags), int((timestamp_sec + 0.25) / hop) + 1)
                if end > start:
                    voiced = float(sum(voice_features.voiced_flags[start:end])) / (end - start) >= MIN_VOICED_RATIO
            (speaking_frames if voiced else silent_frames).append(frame)
        face["speakingFrameCount"] = float(sum(frame.detected for frame in speaking_frames))
        face["silentFrameCount"] = float(sum(frame.detected for frame in silent_frames))
        for label, frames in (("speaking", speaking_frames), ("silent", silent_frames)):
            if any(frame.detected for frame in frames):
                summary = face_log_summary(frames)
                face.update({f"{label}{key[0].upper()}{key[1:]}": value
                             for key, value in face_summary_to_map(summary).items()
                             if key.endswith("LogMean") or key.endswith("LogStd")})

    return BaselineProfile(
        feature_version=2,
        user_id=user_id,
        voice=voice,
        face=face,
        measured_at=datetime.now(timezone.utc).isoformat(),
    )
