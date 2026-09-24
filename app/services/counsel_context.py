"""상담 맥락 조립 — 요청에 빠진 값을 더미로 채운다.

상담봇은 baseline 대비 변화(표정·음성), KOTE 감정 점수, 오늘 일기 요약을 알고
대화를 시작해야 한다. 그런데 이 값들은 다른 파트에서 만들어져 아직 앱에서
넘어오지 않는다. 그래서 값이 비어 있으면 더미로 채워, 프롬프트와 대화 흐름을
먼저 확인할 수 있게 한다.

실제 값이 들어오기 시작하면 `.env`에 `COUNSEL_DUMMY_CONTEXT=false`를 넣으면
더미가 꺼진다. 코드는 건드리지 않아도 된다.

각 값의 출처
    emotions       Step2 분석 — KOTE 텍스트 분류 + 표정·음성 Δ 융합 점수(0~100)
    signals        baseline 대비 변화를 사람이 읽을 문장으로 바꾼 것
    diary_summary  Step2에서 확정한 오늘 일기의 요약
    recent_themes  최근 상담에서 반복된 주제
    incongruent    말로 표현한 감정과 표정·음성이 어긋난다고 판정된 경우
"""

from __future__ import annotations

from app.core.config import get_settings

# 더미값 — 실제 데이터가 붙으면 쓰이지 않는다.
# 값의 "모양"을 보여주는 역할도 하므로, 실제 파트가 맞춰야 할 형식이기도 하다.
_DUMMY_EMOTIONS: dict[str, float] = {
    "슬픔": 62.0,
    "불안": 48.0,
    "피로": 35.0,
}
_DUMMY_SIGNALS: list[str] = [
    "말 속도가 평소보다 느림",
    "목소리 높이가 평소보다 낮음",
]
_DUMMY_DIARY_SUMMARY = "팀 과제에서 맡은 몫을 다 못 했다는 생각이 계속 남았다고 적음"
_DUMMY_RECENT_THEMES: list[str] = ["자기 비난"]


class CounselContext:
    """`build_system_prompt()`에 그대로 넘길 수 있는 맥락 묶음."""

    def __init__(
        self,
        emotions: dict[str, float] | None,
        signals: list[str] | None,
        diary_summary: str | None,
        recent_themes: list[str] | None,
        incongruent: bool,
        used_dummy: bool,
    ) -> None:
        self.emotions = emotions
        self.signals = signals
        self.diary_summary = diary_summary
        self.recent_themes = recent_themes
        self.incongruent = incongruent

        # 응답에 실어 보내, 앱에서 지금 더미로 돌고 있는지 확인할 수 있게 한다.
        self.used_dummy = used_dummy


def resolve(
    emotions: dict[str, float] | None = None,
    signals: list[str] | None = None,
    diary_summary: str | None = None,
    recent_themes: list[str] | None = None,
    incongruent: bool = False,
) -> CounselContext:
    """빈 값을 더미로 채운다. 하나라도 들어왔으면 그 값을 그대로 쓴다.

    항목별로 따로 판단한다. 감정만 먼저 붙고 baseline은 아직인 상황에서도
    붙은 쪽은 실제 값이, 안 붙은 쪽은 더미가 들어간다.
    """
    if not get_settings().counsel_dummy_context:
        return CounselContext(
            emotions=emotions,
            signals=signals,
            diary_summary=diary_summary,
            recent_themes=recent_themes,
            incongruent=incongruent,
            used_dummy=False,
        )

    used_dummy = False

    if not emotions:
        emotions = dict(_DUMMY_EMOTIONS)
        used_dummy = True
    if not signals:
        signals = list(_DUMMY_SIGNALS)
        used_dummy = True
    if not diary_summary:
        diary_summary = _DUMMY_DIARY_SUMMARY
        used_dummy = True
    if not recent_themes:
        recent_themes = list(_DUMMY_RECENT_THEMES)
        used_dummy = True

    return CounselContext(
        emotions=emotions,
        signals=signals,
        diary_summary=diary_summary,
        recent_themes=recent_themes,
        incongruent=incongruent,
        used_dummy=used_dummy,
    )
