from pydantic import BaseModel, Field


class BaselineProfile(BaseModel):
    """baseline 측정(화면 17~21) 결과 — users/{uid}/meta/baseline 문서와 1:1 대응.

    voice/face/measured_at은 그대로 Firestore의 voice/face/measuredAt 필드가 된다
    (FIRESTORE_SCHEMA.md §2 baseline 참고). user_id는 문서 경로에만 쓰이고 문서
    필드에는 포함하지 않는다.
    """

    feature_version: int = Field(default=1, ge=1, description="Baseline feature contract version")
    user_id: str
    voice: dict[str, float] = Field(..., description="음성 기준값. 예: pitchMean, speechRate, energyMean")
    face: dict[str, float] = Field(..., description="표정 기준값. 예: eyeAspectRatio, mouthAspectRatio")
    measured_at: str = Field(..., description="측정 시각 (ISO-8601)")
