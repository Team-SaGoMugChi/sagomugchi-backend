"""Text-only entry point; six-label contract shared with Step2 fusion."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.kote_emotion import MAX_TEXT_LENGTH, MAPPING_VERSION, MODEL_ID, MODEL_REVISION, TextEmotionUnavailable
from app.services.text_emotion import get_text_emotion_classifier

router = APIRouter(prefix="/analyze", tags=["analyze"])


class TextEmotionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class TextEmotionResponse(BaseModel):
    scores: dict[str, float]
    dominant_emotion: str | None
    confidence: float = Field(ge=0, le=1, description="모델 근거 점수; 보정된 정확도나 감정 강도가 아님")
    model_id: str = MODEL_ID
    model_revision: str = MODEL_REVISION
    mapping_version: str = MAPPING_VERSION


@router.post("/text", response_model=TextEmotionResponse)
def analyze_text(request: TextEmotionRequest) -> TextEmotionResponse:
    # Sync handler: CPU inference runs in FastAPI's thread pool.
    try:
        result = get_text_emotion_classifier().classify(request.text)
    except TextEmotionUnavailable as exc:
        raise HTTPException(503, detail={"code": "text_emotion_unavailable", "message": "감정 분석 모델을 사용할 수 없어요. 잠시 후 다시 시도해주세요."}) from exc
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_text", "message": "분석할 텍스트 길이와 내용을 확인해주세요."}) from exc
    return TextEmotionResponse(scores=result.scores, dominant_emotion=result.dominant_emotion,
                               confidence=result.confidence)
