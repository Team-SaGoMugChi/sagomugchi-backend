from pydantic import BaseModel, Field


class FeatureDeltaOut(BaseModel):
    baseline_value: float
    current_value: float
    delta: float
    relative_delta: float | None


class FusionResponse(BaseModel):
    """Step2 감정 키워드·점수 응답. FIRESTORE_SCHEMA.md의 diaries 문서와 대응:
    emotion_keywords → emotionKeywords, emotion_intensity → emotionIntensity
    (emotionStability는 이 fusion 파이프라인이 아직 계산하지 않아 응답에 없음).
    """

    emotion_keywords: list[str] = Field(..., description="점수 상위 감정 라벨")
    emotion_scores: dict[str, float] = Field(..., description="라벨별 점수 (0~100)")
    emotion_intensity: int = Field(..., description="0~100, 텍스트 확신도 + 음성/표정 변화폭")
    text_emotion_scores: dict[str, float] = Field(..., description="텍스트만으로 계산한 라벨 분포 (0~1)")
    voice_delta: dict[str, FeatureDeltaOut] = Field(..., description="baseline 대비 음성 특징 변화")
    face_delta: dict[str, FeatureDeltaOut] = Field(..., description="baseline 대비 표정 특징 변화")
