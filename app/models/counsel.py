from pydantic import BaseModel, Field


class CounselMessage(BaseModel):
    speaker: str = Field(..., description="'user' 또는 'oddo'")
    text: str


class CounselTurnRequest(BaseModel):
    user_text: str
    history: list[CounselMessage] = Field(default_factory=list)
    emotions: dict[str, float] | None = Field(
        None, description="Step2 fusion의 감정 라벨별 점수(0~100)"
    )
    persona: dict | None = Field(None, description="meta/persona 문서")

    # 상담봇이 사용자의 상태를 알고 대화를 시작하기 위한 맥락.
    # 아직 앱에서 넘어오지 않으면 서버가 더미로 채운다(counsel_context.py).
    signals: list[str] | None = Field(
        None,
        description="baseline 대비 변화를 문장으로 바꾼 것. "
        '예: ["말 속도가 평소보다 느림"]',
    )
    diary_summary: str | None = Field(None, description="오늘 일기(Step2 확정본)의 요약")
    recent_themes: list[str] | None = Field(
        None, description='최근 상담에서 반복된 주제. 예: ["자기 비난"]'
    )
    incongruent: bool = Field(
        False, description="말로 표현한 감정과 표정·음성이 어긋난다고 분석된 경우"
    )


class CounselTurnResponse(BaseModel):
    reply: str
    crisis: bool = False

    # 지금 응답이 더미 맥락으로 만들어졌는지. 연동 확인용이라 앱 화면에는 쓰지 않는다.
    used_dummy_context: bool = False
