"""텍스트 감정 + baseline 대비 음성/표정 Δ를 결합해 감정 키워드·점수를 산출.

방법론 원본(_docs/thesis.pdf)은 이 개발 환경에 PDF 렌더링 도구가 없어 직접 확인하지
못했다. 아래 결합 방식은 "카테고리(어떤 감정인가)는 텍스트가 결정하고, 강도(얼마나
강한가)는 음성·표정 Δ가 보정한다"는 통상적인 멀티모달 fusion 패턴을 따른 잠정 구현이다.

TODO(Phase 5): 팀이 논문의 정확한 결합 수식을 공유하면 _delta_magnitude()/emotion_intensity
계산 위주로 교체. text_emotion.py의 모델 교체와 별개로 진행 가능.
"""

from dataclasses import dataclass

from app.services.baseline_delta import FeatureDelta
from app.services.text_emotion import TextEmotionResult, get_text_emotion_classifier

_RELATIVE_DELTA_CLAMP = 3.0  # relative_delta를 이 값으로 클리핑한 뒤 0~1로 정규화
_TOP_KEYWORD_COUNT = 2


@dataclass
class FusionResult:
    emotion_keywords: list[str]  # 점수 상위 라벨들
    emotion_scores: dict[str, float]  # 라벨별 점수 (0~100)
    emotion_intensity: int  # 0~100, 텍스트 확신도 + 음성/표정 변화폭
    text_emotion: TextEmotionResult
    voice_delta: dict[str, FeatureDelta]
    face_delta: dict[str, FeatureDelta]


def _delta_magnitude(deltas: dict[str, FeatureDelta]) -> float:
    """Δ 딕셔너리에서 0~1 스케일의 평균 변화 크기를 뽑아낸다 (baseline 대비 상대 변화량)."""
    if not deltas:
        return 0.0

    magnitudes = [
        min(abs(feature_delta.relative_delta), _RELATIVE_DELTA_CLAMP) / _RELATIVE_DELTA_CLAMP
        for feature_delta in deltas.values()
        if feature_delta.relative_delta is not None
    ]
    return sum(magnitudes) / len(magnitudes) if magnitudes else 0.0


def fuse_emotion(
    text: str,
    voice_delta: dict[str, FeatureDelta],
    face_delta: dict[str, FeatureDelta],
) -> FusionResult:
    text_emotion = get_text_emotion_classifier().classify(text)

    voice_arousal = _delta_magnitude(voice_delta)
    face_arousal = _delta_magnitude(face_delta)
    arousal_sources = [m for m, deltas in ((voice_arousal, voice_delta), (face_arousal, face_delta)) if deltas]
    arousal = sum(arousal_sources) / len(arousal_sources) if arousal_sources else 0.0

    emotion_intensity = round(((text_emotion.confidence + arousal) / 2) * 100)
    emotion_intensity = max(0, min(100, emotion_intensity))

    emotion_scores = {label: round(score * 100, 1) for label, score in text_emotion.scores.items()}
    # Unknown text must not become joy/sadness through dictionary-order ties.
    emotion_keywords = (
        [label for label in sorted(emotion_scores, key=emotion_scores.get, reverse=True)
         if emotion_scores[label] > 0][:_TOP_KEYWORD_COUNT]
        if text_emotion.dominant_emotion is not None else []
    )
    if text_emotion.dominant_emotion is None:
        emotion_intensity = 0

    return FusionResult(
        emotion_keywords=emotion_keywords,
        emotion_scores=emotion_scores,
        emotion_intensity=emotion_intensity,
        text_emotion=text_emotion,
        voice_delta=voice_delta,
        face_delta=face_delta,
    )
