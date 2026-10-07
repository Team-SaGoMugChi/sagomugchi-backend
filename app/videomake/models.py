"""도메인 모델.

pydantic 모델이므로 OddO FastAPI 이식 시 요청/응답 스키마로 그대로 재사용한다.
연출 원칙 중 타입으로 강제할 수 있는 것은 전부 타입으로 강제했다.
프롬프트로만 부탁하면 LLM은 반드시 샌다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .config import (
    CROSSFADE_SECONDS,
    DIALOGUE_MAX_LINES,
    DIALOGUE_MIN_LINES,
    DIALOGUE_MIN_SECONDS,
    CutSeconds,
    dialogue_max_chars,
)

# 클로즈업 계열이 아예 표현 불가능하도록 세 값만 허용한다. (연출 원칙 2)
CameraDistance = Literal["wide", "full", "medium"]

# 컷 감정. 감정 분석 6종 + 감정이 두드러지지 않는 "평온". 컷 그림의 빛·색감·표정과
# 영상의 분위기가 이 값을 따른다(prompts/mood.j2). 일기 장면의 감정이 영상에 드러나게 한다.
CutMood = Literal["기쁨", "슬픔", "분노", "불안", "상처", "당황", "평온"]


class Stage(str, Enum):
    STORYBOARD = "storyboard"
    CHARACTER_SHEET = "character_sheet"
    CUT_IMAGES = "cut_images"
    APPROVAL = "approval"
    VIDEOS = "videos"
    NARRATION = "narration"
    COMPOSE = "compose"


class DiaryInput(BaseModel):
    """파이프라인 입력. OddO의 일기 + 감정분석 결과."""

    text: str
    emotion: dict[str, Any] = Field(default_factory=dict)
    protagonist_name: str | None = None
    # 일기 기록 파트의 전달 JSON(oddo.diary_emotion.v1) — 장면·감정 전환점·대화 칸.
    # 없으면 text·emotion만으로 스토리보드를 만든다.
    handoff: dict[str, Any] | None = None


class CharacterProfile(BaseModel):
    """job 내내 고정되는 인물 정의. 캐릭터 시트와 모든 컷 이미지의 기준."""

    name: str
    appearance: str = Field(
        description="외형 서술(영어). 캐릭터 시트 생성과 컷 프롬프트에 매번 삽입된다."
    )
    voice: str = Field(
        default="",
        description=(
            "목소리 서술(영어). 예: 'deep, low-pitched and rough, a man in his late thirties'. "
            "대사 컷에서 Veo에 그대로 전달된다. 이걸 비워두면 등장인물이 모두 "
            "같은 목소리로 말한다."
        ),
    )


class LocationProfile(BaseModel):
    """job 내내 고정되는 장소 정의. 같은 장소의 컷 그림이 같은 곳으로 보이게 하는 기준.

    컷 그림은 컷마다 따로 그리므로, 장소를 컷마다 다르게 설명하면 같은 강의실이 매번
    다른 방으로 그려진다(실제로 관측됨). 인물처럼 한 번 정의하고 모든 컷에 그대로 넣는다.
    """

    name: str = Field(description="장소 이름(한국어, 짧게). 컷의 location과 정확히 같아야 한다.")
    description: str = Field(
        description=(
            "장소 외형 서술(영어). 바닥·벽·창의 위치·가구 종류와 배치·주요 색·조명 기구. "
            "시간대·빛·인물은 쓰지 않는다. 그 장소의 모든 컷 그림 프롬프트에 그대로 들어간다."
        )
    )


class Distortion(BaseModel):
    """인지왜곡. 사실과 '느껴진 것'을 구조적으로 분리한다. (연출 원칙 6)"""

    fact: str
    felt_as: str
    kind: str


class Line(BaseModel):
    """대사 한 마디. speaker는 스토리보드에 정의된 인물 이름이어야 한다."""

    speaker: str = Field(description="말하는 인물의 이름")
    text: str = Field(description="그 인물이 말하는 한국어 대사 한 마디")


class Cut(BaseModel):
    index: int = Field(ge=1)
    image_prompt: str = Field(description="무엇이 보이는가 (영어)")
    motion_prompt: str = Field(description="컷 길이 동안 무엇이 변하는가 (영어)")
    narration: str | None = Field(
        default=None, description="화면 밖 관찰자 나레이션 (한국어)"
    )
    dialogue: list[Line] = Field(
        default_factory=list, description="인물이 직접 말하는 대사 (한국어)"
    )
    camera_distance: CameraDistance = "full"
    duration_seconds: CutSeconds = 8
    mood: CutMood = "평온"
    # 스토리보드 locations의 name. 없으면 image_prompt만으로 장소를 그린다.
    location: str | None = None

    @property
    def is_dialogue(self) -> bool:
        return bool(self.dialogue)

    @property
    def is_silent(self) -> bool:
        """나레이션도 대사도 없이 화면만 보여주는 컷. 앞 컷의 나레이션이 이어서 깔릴 수 있다."""
        return not self.narration and not self.dialogue

    @model_validator(mode="after")
    def _at_most_one_voice_track(self) -> Cut:
        """나레이션과 대사를 한 컷에 같이 넣지 않는다.

        둘 다 넣으면 서로 묻힌다. 관찰자 목소리와 인물 목소리가 겹치면 거리두기
        구조도 무너진다. 둘 다 없는 컷(무음 컷)은 된다 — 나레이션 글자 수는 컷이 아니라
        나레이션이 이어지는 구간으로 검사한다(narration_windows).
        """
        has_narration = bool(self.narration and self.narration.strip())
        if has_narration and self.dialogue:
            raise ValueError(
                "한 컷에 나레이션과 대사를 함께 넣을 수 없다. 둘 중 하나만 쓴다."
            )

        if self.dialogue and len(self.dialogue) < DIALOGUE_MIN_LINES:
            raise ValueError(
                f"대사가 {len(self.dialogue)}줄뿐이다. 최소 {DIALOGUE_MIN_LINES}줄로 "
                "주고받아야 한다. 한 줄이면 컷의 남는 시간을 모델이 지어낸 대사로 "
                "메운다."
            )
        if len(self.dialogue) > DIALOGUE_MAX_LINES:
            raise ValueError(
                f"대사가 {len(self.dialogue)}줄로 상한 {DIALOGUE_MAX_LINES}줄을 넘는다. "
                f"{self.duration_seconds}초 안에 들어가지 않는다."
            )
        if self.dialogue and self.duration_seconds < DIALOGUE_MIN_SECONDS:
            raise ValueError(
                f"대사 컷이 {self.duration_seconds}초다. 두 줄 이상 주고받으려면 "
                f"{DIALOGUE_MIN_SECONDS}초 이상이어야 한다."
            )
        total = sum(len(line.text) for line in self.dialogue)
        limit = dialogue_max_chars(self.duration_seconds)
        if total > limit:
            raise ValueError(
                f"대사 총 길이가 {total}자로 {self.duration_seconds}초 컷 상한 {limit}자를 "
                "넘는다. 컷 길이 안에 말해지지 않는다."
            )
        return self


class Storyboard(BaseModel):
    protagonist: CharacterProfile
    # 대사 컷에 등장하는 상대역. 캐릭터 시트는 주인공만 만든다.
    supporting: list[CharacterProfile] = Field(default_factory=list)
    distortions: list[Distortion] = Field(default_factory=list)
    locations: list[LocationProfile] = Field(default_factory=list)
    cuts: list[Cut]

    @property
    def characters(self) -> list[CharacterProfile]:
        return [self.protagonist, *self.supporting]

    def character(self, name: str) -> CharacterProfile | None:
        for c in self.characters:
            if c.name == name:
                return c
        return None

    @model_validator(mode="after")
    def _speakers_are_defined(self) -> Storyboard:
        """대사의 화자는 반드시 정의된 인물이어야 한다.

        이름이 어긋나면 목소리 서술을 못 찾아 전원이 같은 목소리로 말하게 된다.
        """
        known = {c.name for c in self.characters}
        for cut in self.cuts:
            for line in cut.dialogue:
                if line.speaker not in known:
                    raise ValueError(
                        f"컷 {cut.index}의 화자 '{line.speaker}'가 인물 목록에 없다. "
                        f"정의된 인물: {sorted(known)}"
                    )
        return self

    @model_validator(mode="after")
    def _locations_are_defined(self) -> Storyboard:
        """컷의 장소는 정의된 장소여야 한다. 이름이 어긋나면 장소 설명을 못 찾는다."""
        known = {loc.name for loc in self.locations}
        for cut in self.cuts:
            if cut.location is not None and cut.location not in known:
                raise ValueError(
                    f"컷 {cut.index}의 장소 '{cut.location}'가 장소 목록에 없다. "
                    f"정의된 장소: {sorted(known)}"
                )
        return self

    def location(self, name: str | None) -> LocationProfile | None:
        for loc in self.locations:
            if loc.name == name:
                return loc
        return None

    def cut(self, index: int) -> Cut:
        for c in self.cuts:
            if c.index == index:
                return c
        raise KeyError(f"컷 {index}이 스토리보드에 없다")

    @property
    def total_seconds(self) -> int:
        return sum(c.duration_seconds for c in self.cuts)

    @property
    def final_seconds(self) -> float:
        """컷 사이 크로스페이드로 겹친 만큼 뺀 실제 영상 길이."""
        return self.total_seconds - CROSSFADE_SECONDS * max(len(self.cuts) - 1, 0)

    def narration_windows(self) -> dict[int, float]:
        """나레이션이 있는 컷 → 그 나레이션이 읽힐 수 있는 시간(초).

        나레이션은 뒤따르는 무음 컷까지 이어서 깔린다. 다음에 나레이션이나 대사가 있는
        컷이 나오면 거기서 끝난다 — 대사와 겹치지 않는다. 컷이 겹치는 크로스페이드만큼 뺀다.
        """
        return narration_windows(
            [(c.duration_seconds, bool(c.narration), bool(c.dialogue)) for c in self.cuts],
            [c.index for c in self.cuts],
        )


def narration_windows(
    cuts: list[tuple[int, bool, bool]], indexes: list[int]
) -> dict[int, float]:
    """(컷 길이, 나레이션 여부, 대사 여부) 목록 → {나레이션 컷 번호: 읽힐 수 있는 시간}."""
    windows: dict[int, float] = {}
    for pos, (seconds, narrated, _) in enumerate(cuts):
        if not narrated:
            continue
        span = [seconds]
        for nxt_seconds, nxt_narrated, nxt_dialogue in cuts[pos + 1 :]:
            if nxt_narrated or nxt_dialogue:
                break
            span.append(nxt_seconds)
        windows[indexes[pos]] = sum(span) - CROSSFADE_SECONDS * len(span)
    return windows


# --- 가드레일 ---------------------------------------------------------------


class Violation(BaseModel):
    field: str
    rule: str
    detail: str

    def __str__(self) -> str:  # LLM 재요청 피드백에 그대로 넣는다
        return f"[{self.field}] {self.rule}: {self.detail}"


# --- 비용 ------------------------------------------------------------------


class CostItem(BaseModel):
    label: str
    quantity: Decimal
    unit: str
    unit_price_usd: Decimal
    subtotal_usd: Decimal


class CostEstimate(BaseModel):
    items: list[CostItem] = Field(default_factory=list)

    @property
    def total_usd(self) -> Decimal:
        return sum((i.subtotal_usd for i in self.items), Decimal(0))


# --- provider 결과 ----------------------------------------------------------


class ImageResult(BaseModel):
    path: str
    cost_usd: Decimal = Decimal(0)
    elapsed_s: float = 0.0


class AudioResult(BaseModel):
    path: str
    duration_s: float = 0.0
    cost_usd: Decimal = Decimal(0)
    elapsed_s: float = 0.0


class VideoHandle(BaseModel):
    """provider 중립 핸들. FastAPI에서는 이걸 DB에 저장하고 워커가 poll한다."""

    cut_index: int
    operation_name: str
    raw: dict[str, Any] = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VideoStatus(BaseModel):
    done: bool
    failed: bool = False
    error: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class VideoResult(BaseModel):
    path: str
    cost_usd: Decimal = Decimal(0)
    elapsed_s: float = 0.0
