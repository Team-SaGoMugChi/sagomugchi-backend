import math

from pydantic import BaseModel, Field, field_validator, model_validator


class PersonaProfile(BaseModel):
    name: str = Field(..., min_length=1, max_length=10)
    tone: str = Field(..., min_length=1, max_length=30)
    traits: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("name", "tone")
    @classmethod
    def validate_single_line_text(cls, value: str):
        value = value.strip()
        if not value or "\n" in value or "\r" in value:
            raise ValueError("persona text must be non-empty and single-line")
        return value

    @field_validator("traits")
    @classmethod
    def validate_traits(cls, value: list[str]):
        cleaned = [trait.strip() for trait in value]
        if any(
            not trait or len(trait) > 20 or "\n" in trait or "\r" in trait
            for trait in cleaned
        ):
            raise ValueError("persona traits must be non-empty single-line text")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("persona traits must not contain duplicates")
        return cleaned


class PsychProfile(BaseModel):
    big5: dict[str, float] | None = Field(
        None, description="IPIP Big Five O/C/E/A/N 점수(0~100)"
    )
    big5_instrument: str | None = Field(None, description="검사 도구와 버전")

    @field_validator("big5")
    @classmethod
    def validate_big5(cls, value: dict[str, float] | None):
        if value is None:
            return value
        if set(value) != {"O", "C", "E", "A", "N"}:
            raise ValueError("big5 must contain exactly O, C, E, A, and N")
        if any(
            not math.isfinite(score) or score < 0 or score > 100
            for score in value.values()
        ):
            raise ValueError("big5 scores must be finite values from 0 to 100")
        return value

    @model_validator(mode="after")
    def require_instrument_for_big5(self):
        if self.big5 is not None and not (self.big5_instrument or "").strip():
            raise ValueError("big5_instrument is required when big5 is provided")
        return self


_SLOT_MAX_ITEMS = 12
_SLOT_MAX_CHARS = 300


def _clean_slots(value: dict[str, str | None] | None) -> dict[str, str] | None:
    """일기 대화 칸에서 빈 칸을 버리고 길이를 제한한다.

    값은 사용자가 말한 그대로라서 내용은 고치지 않는다. 너무 긴 값만 잘라
    프롬프트가 한 칸에 잠식되지 않게 한다.
    """
    if value is None:
        return None
    if len(value) > _SLOT_MAX_ITEMS:
        raise ValueError(f"slots must have at most {_SLOT_MAX_ITEMS} items")
    cleaned: dict[str, str] = {}
    for key, text in value.items():
        key = (key or "").strip()
        text = (text or "").strip()
        if key and text:
            cleaned[key[:20]] = text[:_SLOT_MAX_CHARS]
    return cleaned or None


class CounselMessage(BaseModel):
    speaker: str = Field(..., description="'user' 또는 'oddo'")
    text: str


class CounselTurnRequest(BaseModel):
    user_text: str
    history: list[CounselMessage] = Field(default_factory=list)
    emotions: dict[str, float] | None = Field(
        None, description="Step2 fusion의 감정 라벨별 점수(0~100)"
    )
    persona: PersonaProfile | None = Field(None, description="meta/persona 문서")
    psych_profile: PsychProfile | None = Field(
        None, description="meta/psych에서 검증된 심리검사 결과"
    )

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

    # 일기 대화(handoff `oddo.counsel_context.v1`)에서 넘어오는 사실 재료.
    # 상담봇이 사용자가 실제로 한 말에만 근거해 대화하도록 쓴다.
    slots: dict[str, str | None] | None = Field(
        None,
        description="일기 대화에서 사용자가 말한 칸(육하원칙·그때 기분·기분 변화·지금 기분). "
        "빈 칸은 null",
    )
    emotion_arc: str | None = Field(
        None, max_length=300, description="일기 속 감정 흐름 한 줄 (handoff)"
    )

    @field_validator("slots")
    @classmethod
    def validate_slots(cls, value: dict[str, str | None] | None):
        return _clean_slots(value)


class CounselTurnResponse(BaseModel):
    reply: str
    crisis: bool = False
    # 위험 축 — 앱이 축에 맞는 안내 배너·연락처를 고른다.
    # suicide | danger | harm_others | psychosis | dependence, 위험이 없으면 null
    risk_axis: str | None = None

    # 지금 응답이 더미 맥락으로 만들어졌는지. 연동 확인용이라 앱 화면에는 쓰지 않는다.
    used_dummy_context: bool = False


class CounselReportRequest(BaseModel):
    """상담이 끝난 뒤 리포트를 만들기 위해 보내는 값."""

    messages: list[CounselMessage] = Field(..., description="상담 대화 전체")
    emotions: dict[str, float] | None = Field(
        None, description="Step2 fusion의 감정 라벨별 점수(0~100)"
    )
    diary_summary: str | None = Field(None, description="오늘 일기(Step2 확정본)의 요약")
    slots: dict[str, str | None] | None = Field(
        None, description="일기 대화에서 사용자가 말한 칸 — 리포트 근거 확인용"
    )

    @field_validator("slots")
    @classmethod
    def validate_slots(cls, value: dict[str, str | None] | None):
        return _clean_slots(value)


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