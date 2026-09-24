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


class CounselReportRequest(BaseModel):
    """상담이 끝난 뒤 리포트를 만들기 위해 보내는 값."""

    messages: list[CounselMessage] = Field(..., description="상담 대화 전체")
    emotions: dict[str, float] | None = Field(
        None, description="Step2 fusion의 감정 라벨별 점수(0~100)"
    )
    diary_summary: str | None = Field(None, description="오늘 일기(Step2 확정본)의 요약")


class CounselReport(BaseModel):
    """46번 화면에 그대로 뿌릴 수 있는 형태."""

    headline: str = Field(..., description="오늘을 한 문장으로")
    summary: str = Field(..., description="무슨 일이 있었고 어떻게 느꼈는지 2~3문장")
    moments: list[str] = Field(
        default_factory=list, description="대화 중 스스로 알아차린 점"
    )
    reframe: str = Field("", description="달리 볼 수 있는 관점 한 문장")
    suggestion: str = Field("", description="아주 작은 행동 하나. 없을 수 있음")
    closing: str = Field("", description="마무리 한 문장")