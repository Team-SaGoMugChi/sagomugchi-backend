import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.diary_interview import InterviewMessage

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class HandoffEmotion(BaseModel):
    """Step2 감정 분석(`/diary/step2/analyze`) 결과 — 텍스트·표정·음성 결합본."""

    keywords: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict, description="라벨별 점수 0~100")
    intensity: int | None = Field(None, ge=0, le=100)
    signals: list[str] = Field(default_factory=list, description="baseline 대비 변화 문장")
    incongruent: bool = False


class HandoffRequest(BaseModel):
    """일기 기록(Step2 확인)이 끝난 뒤 영상·상담 파트에 넘길 재료."""

    date: str = Field(..., description="yyyy-MM-dd")
    transcript: str = Field(
        ..., min_length=1, max_length=10000, description="사용자 답변 원문 — 차례마다 줄바꿈"
    )
    diary_text: str | None = Field(None, max_length=10000, description="정제·수정한 일기")
    summary: str | None = Field(None, max_length=1000)
    slots: dict[str, str | None] = Field(default_factory=dict, description="대화 칸")
    conversation: list[InterviewMessage] = Field(default_factory=list, max_length=40)
    emotion: HandoffEmotion = Field(default_factory=HandoffEmotion)

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        if not _DATE.match(value):
            raise ValueError("date must be yyyy-MM-dd")
        return value

    @field_validator("transcript")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("transcript must not be blank")
        return value


class HandoffResponse(BaseModel):
    video: dict[str, Any] = Field(..., description="영상 파트용 — oddo.diary_emotion.v1")
    counsel: dict[str, Any] = Field(..., description="상담 파트용 — oddo.counsel_context.v1")
