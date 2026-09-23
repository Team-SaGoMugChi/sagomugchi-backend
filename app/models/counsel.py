from pydantic import BaseModel, Field


class CounselMessage(BaseModel):
    speaker: str = Field(..., description="'user' 또는 'oddo'")
    text: str


class CounselTurnRequest(BaseModel):
    user_text: str
    history: list[CounselMessage] = Field(default_factory=list)
    emotions: dict[str, float] | None = Field(
        None, description="Step2 fusion의 감정 라벨별 점수"
    )
    persona: dict | None = Field(None, description="meta/persona 문서")


class CounselTurnResponse(BaseModel):
    reply: str
    crisis: bool = False