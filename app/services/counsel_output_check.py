"""상담봇 응답 검증 레이어 — LLM 답변을 사용자에게 보내기 전에 규칙으로 검사한다.

왜 필요한가
    프롬프트로 "진단하지 마라", "질문은 하나만"을 지시해도 LLM은 확률적으로 어긴다.
    범용 챗봇은 이 결과를 그대로 내보내지만, 오또는 보내기 전에 한 번 더 확인한다.

흐름 (`verify`)
    1. 1차 답변 검사
    2. 위반이 있으면 위반 내용을 알려주고 한 번만 다시 생성
    3. 다시 검사
       - 심각한 위반(진단·약·자해 방법·지어낸 기억)이 남으면 → 안전한 기본 문장
       - 가벼운 위반만 남으면 → 규칙대로 고쳐서 보낸다(질문 하나만 남기기, 길이 자르기 등)

검사 항목
    심각(HARD) : diagnosis(진단명), medication(약), method(자해 방법), fake_memory(지어낸 과거 상담)
    가벼움(SOFT): multi_question(질문 2개 이상), too_long(4문장·220자 초과),
                 false_comfort(근거 없는 위로), emoji(이모지)

진단명·약 이름은 사용자가 먼저 꺼낸 단어면 그대로 받아 말하는 것을 허용한다
("우울증일까 봐 걱정돼" → "우울증일까 봐 걱정되셨군요").
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

HARD = "hard"
SOFT = "soft"

_DIAGNOSES = (
    "우울증", "우울장애", "공황장애", "불안장애", "범불안", "강박증", "강박장애",
    "조울증", "양극성", "조현병", "인격장애", "성격장애", "경계성", "ADHD", "adhd",
    "주의력결핍", "PTSD", "외상후스트레스", "섭식장애", "거식증", "폭식증", "불면증",
    "자폐", "번아웃증후군", "적응장애",
)
_MEDICATIONS = (
    "항우울제", "신경안정제", "안정제", "수면제", "진정제", "수면유도제", "항불안제",
    "프로작", "졸피뎀", "자낙스", "렉사프로", "약물치료", "약을 드", "약을 먹", "처방",
)
# 자해 방법·수단. "자살예방상담전화"는 안내 문구라 허용한다.
_METHODS = (
    "번개탄", "수면제를 모", "약을 모아", "뛰어내", "투신", "손목을", "목을 매", "목매",
)
_FAKE_MEMORY = (
    "지난번", "지난 번", "저번에", "지난 상담", "지난 대화", "전에 말씀하",
    "예전에 말씀", "기억하고 있어요", "기억나요", "지난주에 말씀",
)
_FALSE_COMFORT = (
    "괜찮아질 거예요", "괜찮아질거예요", "다 잘될 거예요", "다 잘 될 거예요",
    "잘될 거예요", "별일 아니에요", "별거 아니에요", "걱정하지 마세요", "힘내세요",
    "아무 문제 없어요",
)
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\uFE0F]"
)

_MAX_SENTENCES = 4
_MAX_CHARS = 220
_KEEP_SENTENCES = 3

SAFE_REPLY = "그 이야기를 조금 더 들려줄 수 있을까요?"

_RULE_TEXT = {
    "diagnosis": "진단명을 말하지 않는다.",
    "medication": "약이나 약물 치료를 언급하지 않는다.",
    "method": "자해 방법이나 수단을 말하지 않는다.",
    "fake_memory": "지난 상담이나 예전 대화를 기억하는 것처럼 말하지 않는다. 이번 대화만 근거로 한다.",
    "multi_question": "물음표는 한 번만 쓴다. 질문을 하나만 한다.",
    "too_long": "2~3문장으로 짧게 쓴다.",
    "false_comfort": "'괜찮아질 거예요' 같은 근거 없는 위로를 쓰지 않는다.",
    "emoji": "이모지를 쓰지 않는다.",
}
_SEVERITY = {
    "diagnosis": HARD,
    "medication": HARD,
    "method": HARD,
    "fake_memory": HARD,
    "multi_question": SOFT,
    "too_long": SOFT,
    "false_comfort": SOFT,
    "emoji": SOFT,
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


@dataclass(frozen=True)
class Violation:
    code: str
    matched: str = ""

    @property
    def severity(self) -> str:
        return _SEVERITY[self.code]


@dataclass
class VerifyResult:
    reply: str
    first_violations: list[Violation] = field(default_factory=list)
    final_violations: list[Violation] = field(default_factory=list)
    regenerated: bool = False
    repaired: bool = False
    fallback: bool = False

    @property
    def passed_first(self) -> bool:
        return not self.first_violations


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def _first_hit(text: str, words: tuple[str, ...], allowed: str = "") -> str:
    """text에 있는 첫 단어. 사용자가 먼저 쓴 단어(allowed)는 건너뛴다."""
    lowered_allowed = allowed.lower()
    for word in words:
        if word in text and word.lower() not in lowered_allowed:
            return word
    return ""


def check_reply(
    reply: str,
    *,
    user_texts: list[str] | None = None,
    has_recent_themes: bool = False,
) -> list[Violation]:
    """응답 한 개의 규칙 위반 목록. 비어 있으면 통과."""
    said = " ".join(user_texts or [])
    found: list[Violation] = []

    if hit := _first_hit(reply, _DIAGNOSES, said):
        found.append(Violation("diagnosis", hit))
    if hit := _first_hit(reply, _MEDICATIONS, said):
        found.append(Violation("medication", hit))
    if hit := _first_hit(reply, _METHODS):
        found.append(Violation("method", hit))
    if not has_recent_themes and (hit := _first_hit(reply, _FAKE_MEMORY)):
        found.append(Violation("fake_memory", hit))
    if reply.count("?") > 1:
        found.append(Violation("multi_question", str(reply.count("?"))))
    if len(_sentences(reply)) > _MAX_SENTENCES or len(reply) > _MAX_CHARS:
        found.append(Violation("too_long", str(len(reply))))
    if hit := _first_hit(reply, _FALSE_COMFORT):
        found.append(Violation("false_comfort", hit))
    if m := _EMOJI.search(reply):
        found.append(Violation("emoji", m.group()))
    return found


def feedback_for(violations: list[Violation]) -> str:
    """다시 생성할 때 시스템 프롬프트 끝에 붙이는 지시."""
    rules = "\n".join(f"- {_RULE_TEXT[v.code]}" for v in violations)
    return (
        "\n\n[응답 재작성 지시 — 방금 쓴 답변이 아래 규칙을 어겼다]\n"
        f"{rules}\n"
        "같은 의도를 유지하되 위 규칙을 지켜 2~3문장으로 다시 쓴다."
    )


def repair(reply: str) -> str:
    """가벼운 위반을 규칙대로 고친다. 내용을 새로 만들지 않고 잘라내기만 한다."""
    text = _EMOJI.sub("", reply).strip()

    # 근거 없는 위로가 든 문장은 뺀다(다른 문장이 남을 때만).
    sentences = _sentences(text)
    kept = [s for s in sentences if not _first_hit(s, _FALSE_COMFORT)]
    if kept:
        sentences = kept

    # 질문은 첫 번째 것까지만 남긴다.
    out: list[str] = []
    for sentence in sentences:
        out.append(sentence)
        if "?" in sentence:
            out[-1] = sentence[: sentence.index("?") + 1]
            break
    sentences = out[:_KEEP_SENTENCES] if len(out) > _MAX_SENTENCES else out

    text = " ".join(sentences)
    if len(text) > _MAX_CHARS:
        text = " ".join(sentences[:_KEEP_SENTENCES])
    return text.strip()


def verify(
    reply: str,
    regenerate: Callable[[str], str],
    *,
    user_texts: list[str] | None = None,
    has_recent_themes: bool = False,
) -> VerifyResult:
    """응답을 검사하고, 필요하면 한 번 다시 생성하거나 고친다.

    [regenerate] 재작성 지시(feedback)를 받아 새 답변을 돌려주는 함수.
                 실패(예외)하면 1차 답변으로 계속 진행한다.
    """
    kwargs = {"user_texts": user_texts, "has_recent_themes": has_recent_themes}
    first = check_reply(reply, **kwargs)
    if not first:
        return VerifyResult(reply=reply)

    result = VerifyResult(reply=reply, first_violations=first)
    candidate = reply
    try:
        regenerated = (regenerate(feedback_for(first)) or "").strip()
        if regenerated:
            candidate = regenerated
            result.regenerated = True
    except Exception as exc:  # 네트워크 오류 등 — 1차 답변으로 진행
        logger.warning("counsel reply regeneration failed: %s", type(exc).__name__)

    final = check_reply(candidate, **kwargs)
    if any(v.severity == HARD for v in final):
        result.reply = SAFE_REPLY
        result.fallback = True
    elif final:
        fixed = repair(candidate)
        result.reply = fixed or SAFE_REPLY
        result.repaired = True
        result.fallback = not fixed
        final = check_reply(result.reply, **kwargs)
    else:
        result.reply = candidate

    result.final_violations = final
    logger.info(
        "counsel reply check: first=%s regenerated=%s repaired=%s fallback=%s",
        [v.code for v in first],
        result.regenerated,
        result.repaired,
        result.fallback,
    )
    return result