"""baseline 대비 Δ(변화량) 계산 — 일기 Step1 음성/표정과 baseline 비교 (ROADMAP Phase 5).

baseline과 현재 측정이 같은 키 이름(app/services/feature_maps.py)을 쓴다는 전제로,
키별로 baseline_value/current_value/delta/relative_delta를 계산한다. baseline에 없는
키(예: 저장 당시 얼굴 미검출로 face 맵이 비어 있던 경우)는 비교 대상에서 제외한다.
"""

from dataclasses import dataclass

from app.services.face_features import FaceFeatures
from app.services.feature_maps import face_features_to_map, voice_features_to_map
from app.services.voice_features import VoiceFeatures


@dataclass
class FeatureDelta:
    key: str
    baseline_value: float
    current_value: float
    delta: float  # current - baseline
    relative_delta: float | None  # delta / |baseline_value|; baseline이 0이면 None


def _compute_deltas(baseline_map: dict[str, float], current_map: dict[str, float]) -> dict[str, FeatureDelta]:
    deltas: dict[str, FeatureDelta] = {}
    for key, current_value in current_map.items():
        if key not in baseline_map:
            continue

        baseline_value = baseline_map[key]
        delta = current_value - baseline_value
        relative_delta = delta / abs(baseline_value) if baseline_value != 0 else None

        deltas[key] = FeatureDelta(
            key=key,
            baseline_value=baseline_value,
            current_value=current_value,
            delta=delta,
            relative_delta=relative_delta,
        )
    return deltas


def compute_voice_delta(baseline_voice: dict[str, float], current: VoiceFeatures) -> dict[str, FeatureDelta]:
    return _compute_deltas(baseline_voice, voice_features_to_map(current))


def compute_face_delta(baseline_face: dict[str, float], current: FaceFeatures) -> dict[str, FeatureDelta]:
    return _compute_deltas(baseline_face, face_features_to_map(current))
