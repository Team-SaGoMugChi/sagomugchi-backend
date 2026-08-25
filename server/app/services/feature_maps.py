"""VoiceFeatures/FaceFeatures → Firestore 스키마 키 맵 변환 (FIRESTORE_SCHEMA.md §2 baseline 참고).

baseline 저장(baseline_service)과 일기 Step1 Δ 계산(baseline_delta)이 반드시 같은 키
이름을 써야 두 값을 비교할 수 있어서, 매핑 로직을 여기 하나로 모은다.
"""

from app.services.face_features import FaceFeatures
from app.services.voice_features import VoiceFeatures


def voice_features_to_map(features: VoiceFeatures) -> dict[str, float]:
    result: dict[str, float] = {"energyMean": features.rms_mean}
    if features.f0_mean_hz is not None:
        result["pitchMean"] = features.f0_mean_hz
    if features.speaking_rate_sps is not None:
        result["speechRate"] = features.speaking_rate_sps  # 음절/초 (STT 없이 계산한 근사치)
    return result


def face_features_to_map(features: FaceFeatures) -> dict[str, float]:
    if not features.landmarks_detected:
        return {}
    return {
        "eyeAspectRatio": features.eye_aspect_ratio,
        "mouthAspectRatio": features.mouth_aspect_ratio,
        "mouthWidthRatio": features.mouth_width_ratio,
        "eyebrowRaiseRatio": features.eyebrow_raise_ratio,
    }
