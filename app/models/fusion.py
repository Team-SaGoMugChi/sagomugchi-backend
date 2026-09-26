from typing import Annotated

from pydantic import BaseModel, Field


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Score100 = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class FeatureDeltaOut(BaseModel):
    baseline_value: FiniteFloat
    current_value: FiniteFloat
    delta: FiniteFloat
    relative_delta: FiniteFloat | None


class FusionResponse(BaseModel):
    """Step2 감정 키워드·점수 응답. FIRESTORE_SCHEMA.md의 diaries 문서와 대응:
    emotion_keywords → emotionKeywords, emotion_intensity → emotionIntensity
    (emotionStability는 이 fusion 파이프라인이 아직 계산하지 않아 응답에 없음).
    """

    emotion_keywords: list[str] = Field(..., description="점수 상위 감정 라벨")
    emotion_scores: dict[str, Score100] = Field(..., description="라벨별 점수 (0~100)")
    emotion_intensity: int = Field(..., ge=0, le=100, description="0~100, 텍스트 확신도 + 음성/표정 변화폭")
    text_emotion_scores: dict[str, Probability] = Field(..., description="텍스트만으로 계산한 라벨 분포 (0~1)")
    voice_delta: dict[str, FeatureDeltaOut] = Field(..., description="baseline 대비 음성 특징 변화")
    face_delta: dict[str, FeatureDeltaOut] = Field(..., description="baseline 대비 표정 특징 변화")
    signals: list[str] = Field(default_factory=list, description="상담에 전달할 baseline 대비 변화 설명")
    incongruent: bool = Field(default=False, description="말과 표정·음성의 뚜렷한 불일치 여부")
    incongruence_sources: list[str] = Field(default_factory=list, description="불일치가 감지된 모달리티")
    modalities: list[str] = Field(default_factory=list, description="최종 계산에 실제 반영된 입력")
