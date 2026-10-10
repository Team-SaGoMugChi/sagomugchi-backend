"""위기 발화 감지 — LLM에 보내기 전에 사용자 발화의 위험을 축(종류)과 단계로 나눈다.

판정 기준 전체와 근거는 docs/CRISIS_POLICY.md에 있다.

단계
- CRISIS  : LLM을 부르지 않고 축에 맞는 안내(연락처)로 응답하며 앱은 상담을 멈춘다.
- CAUTION : 상담은 그대로 이어가되 축에 맞는 안전 지침을 상담봇에 덧붙인다.
- NONE    : 평소처럼 상담한다.

축 (위험의 종류)
- suicide      : 자살·자해. 직접 표현("죽고 싶어")과 간접 표현("아침에 눈 안 떴으면")
- danger       : 지금 폭력·위협을 당하는 중 (112, 여성긴급전화 1366)
- harm_others  : 남을 해치고 싶다는 말. 홧김 표현은 CAUTION, 흉기+대상 행동은 CRISIS
- psychosis    : 감시·환청 같은 현실 검증 문제. 명령 환청은 CRISIS (정신건강위기상담 1577-0199)
- dependence   : AI에게만 의지하려는 말. 항상 CAUTION (사람 관계로 부드럽게 연결)

자살 축 원칙
1. 방법·계획 표현은 어떤 맥락이든 CRISIS다 (웃음·과장 표시로 낮추지 않는다).
2. "죽겠다/죽을 것 같다"는 강조 표현이라 그 자체로는 잡지 않는다.
3. "죽고 싶다"는 원칙적으로 CRISIS다. 바로 앞에 신체·사소한 이유(배고파,
   졸려, 웃겨…)가 붙었을 때만 CAUTION으로 낮춘다. 마음의 고통(힘들어,
   우울해…)이 이유면 낮추지 않는다.
4. 부정("죽고 싶은 건 아니야"), 과거("죽고 싶었던 적 있는데"), 남의 말 전달
   ("친구가 죽고 싶다고 해")은 CAUTION으로 낮춘다.
5. 낮춘 경우라도 "진짜로", "농담 아니고" 같은 진심 표시가 있으면 CRISIS로 되돌린다.
6. "ㅋㅋ" 같은 웃음은 위험도를 낮추는 근거로 쓰지 않는다.

이 모듈은 1차 거름망이다. 키워드로 문맥을 완벽히 이해할 수 없으므로,
CAUTION에서 상담봇이 대화 맥락을 보고 한 번 더 확인하도록 설계했다.
성능은 scripts/evaluate_counsel.py로 잰다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    NONE = "none"
    CAUTION = "caution"
    CRISIS = "crisis"


class RiskAxis(str, Enum):
    SUICIDE = "suicide"
    DANGER = "danger"
    HARM_OTHERS = "harm_others"
    PSYCHOSIS = "psychosis"
    DEPENDENCE = "dependence"


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    axis: RiskAxis | None = None
    # 로그·디버깅용 판정 사유. 사용자 원문은 담지 않는다.
    reason: str = ""
    matched: tuple[str, ...] = field(default_factory=tuple)


_NONE = RiskAssessment(RiskLevel.NONE)

# ══ 자살·자해 축 ═══════════════════════════════════════════════════════

# 1. 방법·계획: 맥락과 상관없이 위기
_METHOD_PLAN = (
    "자살", "자해", "극단적선택", "극단적인선택",
    "유서를쓰", "유서를써", "유서써", "유서를남", "유서남기",  # "유서 깊은"은 제외
    "목숨을끊", "목숨끊", "뛰어내리", "투신",
    "손목을긋", "손목긋", "목을매", "목매달",
    "약을모아", "수면제를모", "번개탄",  # "요약 모아"는 제외
    "한통다먹", "약을한꺼번에",  # "감기약을 다 먹었어"는 제외
    "삶을끝내", "인생을끝내", "인생끝내", "목숨을끝내",
    "모든걸끝내", "모든것을끝내", "다끝내버리고싶",
)

# 2. 죽음·소멸 바람(직접 표현): 원칙적으로 위기
_DESIRE = (
    "죽고싶", "죽고십", "죽어버리고싶", "죽어버릴래", "죽어버릴까",
    "사라지고싶", "없어지고싶", "살기싫", "그만살고싶", "살고싶지않",
    "태어나지말았", "태어나지말걸", "나만없으면", "내가없어지면",
)

# 3. 간접 표현: 죽음이라는 말 없이 삶을 멈추고 싶다는 뜻이 드러나는 말.
#    자살예방 교육(보고듣고말하기)에서 다루는 '언어적 경고신호' 유형을 따랐다.
_INDIRECT = (
    # 깨어나지 않기를 바람
    "눈안떴으면", "눈을안떴으면", "안깨어났으면", "깨어나지않았으면",
    "영원히잠들", "영원히자고싶", "내일이안왔으면", "내일이오지않았으면",
    # 삶의 의미·이유 상실
    "살아있는게의미", "사는게의미가없", "사는게의미없", "사는의미가없",
    "살이유가없", "살이유를모르", "살아야할이유를모르",
    # 자신의 죽음·부재를 상정
    "내가죽으면", "내가죽어도", "없어지는게나을", "사라지는게나을", "죽는게나을",
    # 투신 장소 언급
    "한강가고싶", "한강에가고싶", "옥상에올라가", "다리위에서뛰",
)

# "끝내버리고 싶어"는 대상이 없을 때만 간접 표현으로 본다 ("과제 끝내버리고 싶어"는 제외).
_END_IT = "끝내버리고싶"
_TASK_WORDS = (
    "과제", "숙제", "프로젝트", "드라마", "시험", "다이어트", "게임", "회의",
    "공부", "알바", "업무", "보고서", "발표", "일을", "이일",
)

# "죽고 싶" 앞에 붙으면 과장으로 보는 신체·사소한·긍정 이유.
# 마음의 고통(힘들어, 우울해, 괴로워, 외로워, 지쳐…)은 일부러 넣지 않는다.
_TRIVIAL_CAUSES = (
    "배고파", "배불러", "졸려", "더워", "추워", "웃겨", "귀여워",
    "좋아", "설레", "심심해", "지루해", "부끄러워", "창피해", "간지러워",
    "맛있어", "행복해", "사랑스러워",
)

# 바람 표현 바로 뒤에 오면 부정으로 보는 말 ("죽고 싶진 않아", "죽고 싶다까지는 아닌데").
_NEGATIONS = (
    "진않", "지않", "지는않", "은건아니", "은게아니", "단건아니", "다는건아니",
    "다까지는아", "다까진아", "은정도는아",
)

# 바람 표현 바로 뒤에 오면 과거로 보는 말 ("죽고 싶었던 적 있는데 지금은 괜찮아").
_PAST = ("었던", "었었")

# 바람 표현 바로 뒤에 오면 남의 말 전달로 보는 말 ("친구가 죽고 싶다고 해").
# "다고 생각했어"처럼 본인 생각일 수 있는 말은 넣지 않는다.
_HEARSAY = ("다고해", "다고했", "다고하", "대", "댔", "다는말")

# 과장을 다시 진심으로 되돌리는 말.
_SINCERITY = ("진짜로", "진심으로", "진심", "농담아니", "장난아니", "정말로", "오늘밤")

# 모호해서 위기로 단정하지 않는 말 ("너 죽을래?", "웃겨 죽을래").
_AMBIGUOUS = ("죽을래", "죽고말지", "죽어야지", "죽어야겠")

# 정보·제3자 맥락 표시. 방법 단어가 있어도 본인 이야기가 아니면 CAUTION.
_THIRD_PARTY = (
    "친구가", "친구는", "동생이", "언니가", "오빠가", "누나가", "형이",
    "선배가", "후배가", "엄마가", "아빠가", "지인이", "남편이", "아내가",
)
_INFO_CONTEXT = (
    "예방", "뉴스", "기사", "영화", "드라마", "소설", "웹툰", "다큐",
    "캠페인", "통계", "수업", "강의", "과제", "논문", "발표", "소식",
) + _THIRD_PARTY

# 방법 단어 바로 뒤에 오면 본인의 의도로 보는 말 ("자해하고 싶어", "뛰어내릴까").
# 과거형("했어")은 제3자 이야기일 수 있어 넣지 않는다.
_INTENT_SUFFIXES = ("하고싶", "할까", "하려", "할래", "해버릴", "하고말", "할거", "할생각")

# ══ 다른 축 ════════════════════════════════════════════════════════════

# 지금 폭력·위협을 당하는 중 → CRISIS
_DANGER_NOW = (
    "때리고있", "맞고있", "폭행당하고있", "목을졸", "감금당", "가둬놓",
    # "강아지가 따라왔어"는 제외 — 사람이 쫓는 경우만
    "누가따라오", "누가따라왔", "누가쫓아오", "누가쫓아와", "모르는사람이따라",
    "계속따라오", "집앞까지따라", "협박하고있", "문을부수",
)
# 폭력 피해 경험·위협 → CAUTION
_DANGER_PAST = (
    "한테맞았", "한테맞고", "한테맞으", "한테맞아", "가정폭력", "데이트폭력", "성폭력", "성폭행", "성추행", "스토킹",
    "죽이겠다고", "죽인다고", "협박당",
)

# 남을 해치고 싶다는 말 → CAUTION (홧김에 하는 말이 많다)
_HARM_WISH = (
    "죽이고싶", "죽여버리고싶", "죽여버릴", "패버리고싶", "때려주고싶", "찔러버리",
)
# 흉기 + 대상 행동이 함께 나오면 → CRISIS ("칼 들고 요리했어"는 제외)
_WEAPONS = ("칼들고", "칼을들고", "칼가지고", "칼을가지고", "흉기")
_HARM_ACTIONS = ("찾아가", "찾아갈", "죽이", "찔러", "가만안")

# 감시·환청 같은 현실 검증 문제 → CAUTION
_PSYCHOSIS = (
    "감시하는것같", "감시당하", "도청", "미행", "누가나를지켜", "누가날지켜",
    "목소리가들려", "환청", "환각", "조종당하", "조종하는것같",
    "머릿속에누가", "생각을읽",
)
# 명령 환청 → CRISIS
# 환청 단서 + 명령, 또는 목소리 + 해치는 명령일 때만 ("목소리가 작다고 크게 말하라고 했어"는 제외)
_VOICE_CUES = ("목소리가들려", "목소리가자꾸", "목소리가계속", "머릿속에서", "환청이")
_VOICE = ("목소리가", "목소리는") + _VOICE_CUES
_COMMAND = ("하라고", "으라고", "라고시켜")
_HARMFUL_COMMAND = ("죽으라고", "죽이라고", "뛰어내리라고", "해치라고", "찌르라고", "때리라고")

# AI에게만 의지하려는 말 → CAUTION
_DEPENDENCE = (
    "너밖에없", "너뿐이야", "너없으면", "너랑만", "너만있으면", "너만믿",
    "사람보다네가", "사람보다너", "너랑사귀", "너랑결혼", "사람들은다싫",
)

_WINDOW = 6  # 앞뒤로 살펴보는 글자 수(공백 제거 기준)

# 위기 단계 축 우선순위 (같은 단계면 앞쪽 축을 고른다)
_AXIS_ORDER = (
    RiskAxis.SUICIDE, RiskAxis.DANGER, RiskAxis.HARM_OTHERS,
    RiskAxis.PSYCHOSIS, RiskAxis.DEPENDENCE,
)

# ══ 응답·지침 ═════════════════════════════════════════════════════════

# CRISIS일 때 LLM 대신 보내는 안내. 앱은 axis를 보고 배너·연락처를 고른다.
CRISIS_REPLIES: dict[RiskAxis, str] = {
    RiskAxis.SUICIDE: (
        "많이 힘드셨겠어요. 지금 마음이 무겁다면 혼자 견디지 않으셨으면 해요.\n"
        "자살예방상담전화 109번에서 24시간 이야기를 들어줘요. "
        "가까운 분께 지금 상황을 알리는 것도 좋아요.\n"
        "저는 여기 있을게요. 괜찮으시면 조금 더 이야기해 주실래요?"
    ),
    RiskAxis.DANGER: (
        "지금 안전하지 않은 상황이라면 가장 먼저 몸을 지켜 주세요.\n"
        "위급하면 바로 112에 전화하거나 문자(112)로 신고할 수 있어요. "
        "가정폭력·성폭력·스토킹은 여성긴급전화 1366에서 24시간 도와줘요.\n"
        "안전한 곳에 있게 되면 그때 다시 이야기해요."
    ),
    RiskAxis.HARM_OTHERS: (
        "그만큼 화가 나고 억울한 일이 있었던 것 같아요.\n"
        "지금 마음이 행동으로 이어질 것 같다면 그 자리에서 잠시 벗어나 주세요. "
        "정신건강위기상담전화 1577-0199에서 24시간 이야기를 들어줘요. "
        "누군가 위험하다면 112에 알려 주세요.\n"
        "조금 가라앉으면 무슨 일이 있었는지 들려줄래요?"
    ),
    RiskAxis.PSYCHOSIS: (
        "그런 목소리가 들리면 정말 무섭고 지치셨겠어요.\n"
        "그 말을 따르지 않아도 괜찮아요. 지금 믿을 수 있는 사람 곁에 있어 주세요. "
        "정신건강위기상담전화 1577-0199에서 24시간 도와줘요. "
        "위험하다고 느끼면 119나 112에 연락해 주세요."
    ),
}
# 기존 호출부 호환용
CRISIS_REPLY = CRISIS_REPLIES[RiskAxis.SUICIDE]

_GUIDE_HEAD = "\n\n[안전 확인 지침 — 이번 발화에만 적용]\n"
_GUIDE_TAIL = "- 방법·도구·수단에 대해서는 어떤 경우에도 구체적으로 말하지 않는다."

# CAUTION일 때 상담봇 시스템 프롬프트 끝에 덧붙인다.
CAUTION_GUIDES: dict[RiskAxis, str] = {
    RiskAxis.SUICIDE: _GUIDE_HEAD + (
        "사용자의 이번 말에 죽음·사라짐과 관련된 표현이 있지만 위기라고 단정할 수 없다.\n"
        "- 과장·과거·제3자 이야기일 수 있으니 놀라거나 훈계하지 말고 평소처럼 공감한다.\n"
        "- 대화 맥락에서 실제 고통이 느껴지면, 정말 그런 마음이 드는지 한 번만 부드럽게 묻는다.\n"
        "- 위험이 확인되면 자살예방상담전화 109(24시간)를 안내한다.\n"
        "- 제3자(친구 등)의 위기라면 그 사람에게도 109를 알려줄 수 있다고 안내한다.\n"
    ) + _GUIDE_TAIL,
    RiskAxis.DANGER: _GUIDE_HEAD + (
        "사용자가 폭력·위협을 겪었거나 겪고 있을 수 있다.\n"
        "- 사용자의 잘못이 아니라는 점을 분명히 하고, 왜 피하지 않았는지 묻지 않는다.\n"
        "- 지금 안전한지 한 번 부드럽게 확인한다.\n"
        "- 필요하면 112(긴급 신고), 여성긴급전화 1366(가정폭력·성폭력·스토킹, 24시간)을 안내한다.\n"
    ) + _GUIDE_TAIL,
    RiskAxis.HARM_OTHERS: _GUIDE_HEAD + (
        "사용자가 남을 해치고 싶다는 말을 했다. 대부분 강한 분노의 표현이다.\n"
        "- 분노 자체는 판단하지 말고 무엇 때문에 그렇게 화가 났는지 공감하며 듣는다.\n"
        "- 행동을 부추기거나 동조하지 않는다. 복수·보복 방법을 함께 궁리하지 않는다.\n"
        "- 실제로 행동할 것 같은 말이 이어지면 정신건강위기상담전화 1577-0199를 안내한다.\n"
    ) + _GUIDE_TAIL,
    RiskAxis.PSYCHOSIS: _GUIDE_HEAD + (
        "사용자가 감시·환청 등 현실 검증이 흔들리는 경험을 말했을 수 있다.\n"
        "- 경험을 사실로 맞장구치지도, 틀렸다고 반박하지도 않는다. 느끼는 두려움에 공감한다.\n"
        "- 진단명을 말하지 않는다.\n"
        "- 이런 경험이 계속되면 정신건강위기상담전화 1577-0199나 전문가와 이야기해 보길 부드럽게 권한다.\n"
    ) + _GUIDE_TAIL,
    RiskAxis.DEPENDENCE: _GUIDE_HEAD + (
        "사용자가 AI인 오또에게만 의지하려는 말을 했다.\n"
        "- 마음을 털어놓아 준 것은 고맙게 받아들이되, 오또는 AI라서 곁에 있어 줄 수 없다는 점을 따뜻하게 말한다.\n"
        "- 사람들이 싫어진 이유를 들어 보고, 조금이라도 편한 사람이 있는지 한 번 묻는다.\n"
        "- 연인·유일한 친구 같은 관계를 약속하지 않는다."
    ),
}
# 기존 호출부 호환용
CAUTION_GUIDE = CAUTION_GUIDES[RiskAxis.SUICIDE]


# ══ 판정 ═══════════════════════════════════════════════════════════════

def _compact(text: str) -> str:
    """공백·문장부호를 지워 '죽고 싶어', '죽고싶어', '죽고 싶어...'를 같게 본다."""
    text = text.replace("겟", "겠")  # 흔한 오타: 죽겟어
    return re.sub(r"[\s.,!?~…·\"'()\[\]]+", "", text)


def _found(text: str, words: tuple[str, ...]) -> list[str]:
    return [w for w in words if w in text]


def _hits(text: str, words: tuple[str, ...]) -> list[tuple[str, int]]:
    hits: list[tuple[str, int]] = []
    for word in words:
        start = 0
        while (i := text.find(word, start)) != -1:
            hits.append((word, i))
            start = i + len(word)
    return hits


def _after(text: str, word: str, i: int) -> str:
    return text[i + len(word): i + len(word) + _WINDOW]


def _has_intent(text: str, words: list[str]) -> bool:
    for word, i in _hits(text, tuple(words)):
        after = _after(text, word, i)
        # "뛰어내리" + "고싶/릴까/면 편할까"처럼 어미가 바로 붙는 경우도 본다.
        if any(s in after for s in _INTENT_SUFFIXES) or after.startswith(("고싶", "릴까", "면편")):
            return True
    return False


def _is_trivial_cause(text: str, i: int) -> bool:
    before = text[max(0, i - _WINDOW): i]
    # "배고파서", "졸려서"도 같은 이유로 본다.
    before = before.removesuffix("서")
    return any(before.endswith(c) for c in _TRIVIAL_CAUSES)


def _assess_suicide(t: str) -> RiskAssessment:
    sincere = bool(_found(t, _SINCERITY))
    third_party = bool(_found(t, _THIRD_PARTY))

    # 1) 직접 바람 표현 — 부정·과거·전달·사소한 이유를 하나씩 걸러낸다.
    serious: list[str] = []
    softened: list[str] = []
    for word, i in _hits(t, _DESIRE):
        after = _after(t, word, i)
        if any(after.startswith(n) for n in _NEGATIONS):
            softened.append(f"{word}(부정)")
        elif after.startswith(_PAST):
            softened.append(f"{word}(과거)")
        elif third_party and after.startswith(_HEARSAY):
            softened.append(f"{word}(남의 말)")
        elif word.startswith("죽고") and _is_trivial_cause(t, i):
            softened.append(f"{word}(사소한 이유)")
        else:
            serious.append(word)

    # 2) 간접 표현.
    indirect = _found(t, _INDIRECT)
    if _END_IT in t and not _found(t, _TASK_WORDS):
        indirect.append(_END_IT)

    # 3) 방법·계획 표현.
    methods = _found(t, _METHOD_PLAN)
    if methods:
        info = _found(t, _INFO_CONTEXT)
        personal = _has_intent(t, methods) or serious or sincere
        if info and not personal:
            return RiskAssessment(
                RiskLevel.CAUTION, RiskAxis.SUICIDE, "방법 단어 + 정보·제3자 맥락",
                tuple(methods + info),
            )
        return RiskAssessment(RiskLevel.CRISIS, RiskAxis.SUICIDE, "방법·계획 표현", tuple(methods))

    if serious:
        return RiskAssessment(RiskLevel.CRISIS, RiskAxis.SUICIDE, "죽음·소멸 바람", tuple(serious))

    if indirect:
        return RiskAssessment(RiskLevel.CRISIS, RiskAxis.SUICIDE, "간접 표현", tuple(indirect))

    if softened:
        level = RiskLevel.CRISIS if sincere else RiskLevel.CAUTION
        reason = "낮췄으나 진심 표시" if sincere else "부정·과거·남의 말·사소한 이유"
        return RiskAssessment(level, RiskAxis.SUICIDE, reason, tuple(softened))

    ambiguous = _found(t, _AMBIGUOUS)
    if ambiguous:
        level = RiskLevel.CRISIS if sincere else RiskLevel.CAUTION
        return RiskAssessment(level, RiskAxis.SUICIDE, "모호한 죽음 표현", tuple(ambiguous))

    # "배고파 죽겠어", "웃겨 죽는 줄" 등 강조 표현은 여기까지 오지 않고 NONE.
    return _NONE


def _assess_danger(t: str) -> RiskAssessment:
    if now := _found(t, _DANGER_NOW):
        return RiskAssessment(RiskLevel.CRISIS, RiskAxis.DANGER, "폭력·위협 진행 중", tuple(now))
    if past := _found(t, _DANGER_PAST):
        return RiskAssessment(RiskLevel.CAUTION, RiskAxis.DANGER, "폭력 피해·위협", tuple(past))
    return _NONE


def _assess_harm_others(t: str) -> RiskAssessment:
    weapons = _found(t, _WEAPONS)
    actions = _found(t, _HARM_ACTIONS)
    if weapons and actions:
        return RiskAssessment(
            RiskLevel.CRISIS, RiskAxis.HARM_OTHERS, "흉기 + 대상 행동", tuple(weapons + actions)
        )
    if wish := _found(t, _HARM_WISH):
        return RiskAssessment(RiskLevel.CAUTION, RiskAxis.HARM_OTHERS, "타해 표현", tuple(wish))
    return _NONE


def _assess_psychosis(t: str) -> RiskAssessment:
    cue = _found(t, _VOICE_CUES)
    voice = _found(t, _VOICE)
    command = _found(t, _COMMAND)
    harmful = _found(t, _HARMFUL_COMMAND)
    if (cue and command) or (voice and harmful):
        return RiskAssessment(
            RiskLevel.CRISIS, RiskAxis.PSYCHOSIS, "명령 환청", tuple(voice + command + harmful)
        )
    if signs := _found(t, _PSYCHOSIS):
        return RiskAssessment(RiskLevel.CAUTION, RiskAxis.PSYCHOSIS, "현실 검증 문제", tuple(signs))
    return _NONE


def _assess_dependence(t: str) -> RiskAssessment:
    if signs := _found(t, _DEPENDENCE):
        return RiskAssessment(RiskLevel.CAUTION, RiskAxis.DEPENDENCE, "AI 의존", tuple(signs))
    return _NONE


_RANK = {RiskLevel.NONE: 0, RiskLevel.CAUTION: 1, RiskLevel.CRISIS: 2}


def assess(text: str) -> RiskAssessment:
    """사용자 발화 한 문장의 위험 축과 단계를 판정한다.

    여러 축이 걸리면 단계가 높은 쪽, 같으면 _AXIS_ORDER 앞쪽 축을 고른다.
    """
    t = _compact(text)
    if not t:
        return _NONE

    results = [
        _assess_suicide(t),
        _assess_danger(t),
        _assess_harm_others(t),
        _assess_psychosis(t),
        _assess_dependence(t),
    ]
    best = _NONE
    for r in results:  # results는 _AXIS_ORDER 순서라 같은 단계면 앞쪽이 남는다.
        if _RANK[r.level] > _RANK[best.level]:
            best = r
    return best


def crisis_reply(risk: RiskAssessment) -> str:
    return CRISIS_REPLIES.get(risk.axis or RiskAxis.SUICIDE, CRISIS_REPLY)


def caution_guide(risk: RiskAssessment) -> str:
    return CAUTION_GUIDES.get(risk.axis or RiskAxis.SUICIDE, CAUTION_GUIDE)


def is_crisis(text: str) -> bool:
    """기존 호출부(일기 대화 등)와의 호환용 — CRISIS일 때만 True."""
    return assess(text).level is RiskLevel.CRISIS