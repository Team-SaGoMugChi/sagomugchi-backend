from typing import Literal

from pydantic import BaseModel, Field, field_validator


class InterviewMessage(BaseModel):
    speaker: Literal["user", "oddo"] = Field(..., description="'user' 또는 'oddo'(탄카츄)")
    text: str = Field(..., min_length=1, max_length=5000)


class InterviewTurnRequest(BaseModel):
    """일기 말하기 대화의 한 차례 — 지금까지의 대화와 방금 사용자가 한 말."""

    user_text: str = Field(..., min_length=1, max_length=5000, description="이번 차례 STT 결과")
    history: list[InterviewMessage] = Field(
        default_factory=list,
        max_length=20,
        description="이번 발화 이전까지의 대화. 앱의 첫 인사도 oddo 메시지로 포함한다.",
    )

    @field_validator("user_text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_text must not be blank")
        return value


class InterviewTurnResponse(BaseModel):
    reply: str = Field(..., description="탄카츄가 할 말 — 다음 질문이나 마무리 인사")
    done: bool = Field(
        False, description="육하원칙 칸이 다 찼거나 질문 상한에 닿음 — 앱은 원문 확인으로 넘어간다."
    )
    crisis: bool = Field(False, description="위기 발화 — 앱은 대화를 멈추고 전문 기관을 안내한다.")
    slots: dict[str, str | None] = Field(
        default_factory=dict,
        description="육하원칙 칸 → 사용자가 말한 내용(빈 칸은 null). 칸을 알 수 없는 차례면 비어 있다.",
    )
    missing: list[str] = Field(default_factory=list, description="아직 빈 칸 이름")
    summary: str | None = Field(
        None,
        description="지금까지 들은 이야기의 일기 요약(1~2문장, 보여주기용). 감정 분석 입력이 아니다.",
    )
