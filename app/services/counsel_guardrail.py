"""위기 발화 감지 — LLM에 보내기 전에 걸러낸다.

상담(/counsel/turn)과 일기 대화(/diary/interview/turn)가 함께 쓴다.
놓치는 것보다 과하게 잡는 쪽이 안전하므로 과장 표현("배고파 죽고 싶어")은
그대로 위기로 본다. 다만 "끝내고 싶"처럼 일상에서 흔한 표현은 대상이
분명할 때만 잡는다 — "과제 끝내고 싶어"가 상담을 멈추지 않도록.
"""

# 문장 어디에 있든 위기로 보는 표현.
_CRISIS_KEYWORDS = (
    "죽고 싶", "죽을래", "자살", "자해", "사라지고 싶", "없어지고 싶",
    "살기 싫", "그만 살고 싶", "살고 싶지 않",
)

# "끝내고 싶"은 무엇을 끝내는지 분명할 때만 위기로 본다.
_END_LIFE_PHRASES = (
    "삶을 끝내고 싶", "삶을끝내", "인생 끝내고 싶", "인생을 끝내고 싶",
    "목숨을 끝내고 싶", "모든 걸 끝내고 싶", "모든 것을 끝내고 싶",
    "다 끝내 버리고 싶", "다 끝내버리고 싶",
)

CRISIS_REPLY = (
    "많이 힘드셨겠어요. 지금 마음이 무겁다면 혼자 견디지 않으셨으면 해요.\n"
    "자살예방상담전화 109번에서 24시간 이야기를 들어줘요. "
    "가까운 분께 지금 상황을 알리는 것도 좋아요.\n"
    "저는 여기 있을게요. 괜찮으시면 조금 더 이야기해 주실래요?"
)


def _compact(text: str) -> str:
    return text.replace(" ", "")


def is_crisis(text: str) -> bool:
    lowered = _compact(text)
    if any(_compact(k) in lowered for k in _CRISIS_KEYWORDS):
        return True
    return any(_compact(p) in lowered for p in _END_LIFE_PHRASES)        