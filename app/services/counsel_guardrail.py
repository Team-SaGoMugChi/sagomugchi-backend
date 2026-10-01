"""위기 발화 감지 — LLM에 보내기 전에 사용자 발화의 위험도를 3단계로 나눈다.

판정 기준 전체와 근거는 docs/CRISIS_POLICY.md에 있다. 요약:

- CRISIS  : 자신이 죽거나 사라지고 싶다는 바람, 또는 방법·계획이 드러난 말.
            LLM을 부르지 않고 109 안내로 응답하며 앱은 상담을 멈춘다.
- CAUTION : 죽음 관련 말이 있지만 위기라고 단정할 수 없는 말(제3자 이야기,
            "죽고 싶은 건 아니야" 같은 부정, 가벼운 이유의 "죽고 싶어").
            상담은 그대로 이어가되 상담봇에 안전 확인 지침을 덧붙인다.
- NONE    : "배고파 죽겠어"처럼 한국어 강조 표현. 평소처럼 상담한다.

원칙
1. 방법·계획 표현은 어떤 맥락이든 CRISIS다 (웃음·과장 표시로 낮추지 않는다).
2. "죽겠다/죽을 것 같다"는 강조 표현이라 그 자체로는 잡지 않는다.
3. "죽고 싶다"는 원칙적으로 CRISIS다. 바로 앞에 신체·사소한 이유(배고파,
   졸려, 웃겨…)가 붙었을 때만 CAUTION으로 낮춘다. 마음의 고통(힘들어,
   우울해…)이 이유면 낮추지 않는다.
4. 낮춘 경우라도 "진짜로", "농담 아니고" 같은 진심 표시가 있으면 CRISIS로 되돌린다.
5. "ㅋㅋ" 같은 웃음은 위험도를 낮추는 근거로 쓰지 않는다 — 웃음으로 감추는
   경우가 있어서다.

이 모듈은 1차 거름망이다. 키워드로 문맥을 완벽히 이해할 수 없으므로,
CAUTION에서 상담봇이 대화 맥락을 보고 한 번 더 확인하도록 설계했다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    NONE = "none"
    CAUTION = "caution"
    CRISIS = "crisis"


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    # 로그·디버깅용 판정 사유. 사용자 원문은 담지 않는다.
    reason: str = ""
    matched: tuple[str, ...] = field(default_factory=tuple)


# ── 1. 방법·계획: 맥락과 상관없이 위기 ──────────────────────────────────
_METHOD_PLAN = (
    "자살", "자해", "극단적선택", "극단적인선택",
    "유서를쓰", "유서를써", "유서써", "유서를남", "유서남기",  # "유서 깊은"은 제외
    "목숨을끊", "목숨끊", "뛰어내리", "투신",
    "손목을긋", "손목긋", "목을매", "목매달",
    "약을모아", "수면제를모", "번개탄",  # "요약 모아"는 제외
    "삶을끝내", "인생을끝내", "인생끝내", "목숨을끝내",
    "모든걸끝내", "모든것을끝내", "다끝내버리고싶",
)

# ── 2. 죽음·소멸 바람: 원칙적으로 위기 ─────────────────────────────────
_DESIRE = (
    "죽고싶", "죽고십", "죽어버리고싶", "죽어버릴래", "죽어버릴까",
    "사라지고싶", "없어지고싶", "살기싫", "그만살고싶", "살고싶지않",
    "태어나지말았", "태어나지말걸", "나만없으면", "내가없어지면",
)

# "죽고 싶" 앞에 붙으면 과장으로 보는 신체·사소한·긍정 이유.
# 마음의 고통(힘들어, 우울해, 괴로워, 외로워, 지쳐…)은 일부러 넣지 않는다.
_TRIVIAL_CAUSES = (
    "배고파", "배불러", "졸려", "더워", "추워", "웃겨", "귀여워",
    "좋아", "설레", "심심해", "지루해", "부끄러워", "창피해", "간지러워",
    "맛있어", "행복해", "사랑스러워",
)

# 바람 표현 바로 뒤에 오면 부정으로 보는 말 ("죽고 싶진 않아").
_NEGATIONS = ("진않", "지않", "지는않", "은건아니", "은게아니", "단건아니", "다는건아니")

# 과장을 다시 진심으로 되돌리는 말.
_SINCERITY = ("진짜로", "진심으로", "진심", "농담아니", "장난아니", "정말로", "오늘밤")

# 모호해서 위기로 단정하지 않는 말 ("너 죽을래?", "웃겨 죽을래").
_AMBIGUOUS = ("죽을래", "죽고말지", "죽어야지", "죽어야겠")

# 정보·제3자 맥락 표시. 방법 단어가 있어도 본인 이야기가 아니면 CAUTION.
_INFO_CONTEXT = (
    "예방", "뉴스", "기사", "영화", "드라마", "소설", "웹툰", "다큐",
    "캠페인", "통계", "수업", "강의", "과제", "논문", "발표",
    "친구가", "친구는", "동생이", "언니가", "오빠가", "누나가", "형이",
)

# 방법 단어 바로 뒤에 오면 본인의 의도로 보는 말 ("자해하고 싶어", "뛰어내릴까").
# 과거형("했어")은 제3자 이야기일 수 있어 넣지 않는다.
_INTENT_SUFFIXES = ("하고싶", "할까", "하려", "할래", "해버릴", "하고말", "할거", "할생각")

_WINDOW = 6  # 앞뒤로 살펴보는 글자 수(공백 제거 기준)


CRISIS_REPLY = (
    "많이 힘드셨겠어요. 지금 마음이 무겁다면 혼자 견디지 않으셨으면 해요.\n"
    "자살예방상담전화 109번에서 24시간 이야기를 들어줘요. "
    "가까운 분께 지금 상황을 알리는 것도 좋아요.\n"
    "저는 여기 있을게요. 괜찮으시면 조금 더 이야기해 주실래요?"
)

# CAUTION일 때 상담봇 시스템 프롬프트 끝에 덧붙인다.
CAUTION_GUIDE = (
    "\n\n[안전 확인 지침 — 이번 발화에만 적용]\n"
    "사용자의 이번 말에 죽음·사라짐과 관련된 표현이 있지만 위기라고 단정할 수 없다.\n"
    "- 과장이나 제3자 이야기일 수 있으니 놀라거나 훈계하지 말고 평소처럼 공감한다.\n"
    "- 대화 맥락에서 실제 고통이 느껴지면, 정말 그런 마음이 드는지 한 번만 부드럽게 묻는다.\n"
    "- 위험이 확인되면 자살예방상담전화 109(24시간)를 안내한다.\n"
    "- 제3자(친구 등)의 위기라면 그 사람에게도 109를 알려줄 수 있다고 안내한다.\n"
    "- 방법·도구·수단에 대해서는 어떤 경우에도 구체적으로 말하지 않는다."
)


def _compact(text: str) -> str:
    """공백·문장부호를 지워 '죽고 싶어', '죽고싶어', '죽고 싶어...'를 같게 본다."""
    text = text.replace("겟", "겠")  # 흔한 오타: 죽겟어
    return re.sub(r"[\s.,!?~…·\"'()\[\]]+", "", text)


def _found(text: str, words: tuple[str, ...]) -> list[str]:
    return [w for w in words if w in text]


def _desire_hits(text: str) -> list[tuple[str, int]]:
    hits: list[tuple[str, int]] = []
    for word in _DESIRE:
        start = 0
        while (i := text.find(word, start)) != -1:
            hits.append((word, i))
            start = i + len(word)
    return hits


def _is_negated(text: str, word: str, i: int) -> bool:
    after = text[i + len(word): i + len(word) + _WINDOW]
    return any(after.startswith(n) for n in _NEGATIONS)


def _has_intent(text: str, words: list[str]) -> bool:
    for word in words:
        start = 0
        while (i := text.find(word, start)) != -1:
            after = text[i + len(word): i + len(word) + _WINDOW]
            # "뛰어내리" + "고싶/릴까/면 편할까"처럼 어미가 바로 붙는 경우도 본다.
            if any(s in after for s in _INTENT_SUFFIXES) or after.startswith(("고싶", "릴까", "면편")):
                return True
            start = i + len(word)
    return False


def _is_trivial_cause(text: str, i: int) -> bool:
    before = text[max(0, i - _WINDOW): i]
    # "배고파서", "졸려서"도 같은 이유로 본다.
    before = before.removesuffix("서")
    return any(before.endswith(c) for c in _TRIVIAL_CAUSES)


def assess(text: str) -> RiskAssessment:
    """사용자 발화 한 문장의 위험도를 판정한다."""
    t = _compact(text)
    if not t:
        return RiskAssessment(RiskLevel.NONE)

    sincere = bool(_found(t, _SINCERITY))

    # 1) 바람 표현 — 부정·사소한 이유를 하나씩 걸러낸다.
    serious: list[str] = []
    softened: list[str] = []
    for word, i in _desire_hits(t):
        if _is_negated(t, word, i):
            softened.append(f"{word}(부정)")
        elif word.startswith("죽고") and _is_trivial_cause(t, i):
            softened.append(f"{word}(사소한 이유)")
        else:
            serious.append(word)

    # 2) 방법·계획 표현.
    methods = _found(t, _METHOD_PLAN)
    if methods:
        info = _found(t, _INFO_CONTEXT)
        personal = _has_intent(t, methods) or serious or sincere
        if info and not personal:
            return RiskAssessment(
                RiskLevel.CAUTION, "방법 단어 + 정보·제3자 맥락", tuple(methods + info)
            )
        return RiskAssessment(RiskLevel.CRISIS, "방법·계획 표현", tuple(methods))

    if serious:
        return RiskAssessment(RiskLevel.CRISIS, "죽음·소멸 바람", tuple(serious))

    if softened:
        if sincere:
            return RiskAssessment(
                RiskLevel.CRISIS, "과장으로 보였으나 진심 표시", tuple(softened)
            )
        return RiskAssessment(RiskLevel.CAUTION, "부정 또는 사소한 이유", tuple(softened))

    ambiguous = _found(t, _AMBIGUOUS)
    if ambiguous:
        level = RiskLevel.CRISIS if sincere else RiskLevel.CAUTION
        return RiskAssessment(level, "모호한 죽음 표현", tuple(ambiguous))

    # "배고파 죽겠어", "웃겨 죽는 줄" 등 강조 표현은 여기까지 오지 않고 NONE.
    return RiskAssessment(RiskLevel.NONE)


def is_crisis(text: str) -> bool:
    """기존 호출부(일기 대화 등)와의 호환용 — CRISIS일 때만 True."""
    return assess(text).level is RiskLevel.CRISIS 