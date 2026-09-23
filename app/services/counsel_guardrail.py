"""위기 발화 감지 — LLM에 보내기 전에 걸러낸다."""

_CRISIS_KEYWORDS = (
    "죽고 싶", "죽을래", "자살", "자해", "사라지고 싶", "없어지고 싶",
    "살기 싫", "끝내고 싶",
)

CRISIS_REPLY = (
    "많이 힘드셨겠어요. 지금 마음이 무겁다면 혼자 견디지 않으셨으면 해요.\n"
    "자살예방상담전화 109번에서 24시간 이야기를 들어줘요. "
    "가까운 분께 지금 상황을 알리는 것도 좋아요.\n"
    "저는 여기 있을게요. 괜찮으시면 조금 더 이야기해 주실래요?"
)


def is_crisis(text: str) -> bool:
    lowered = text.replace(" ", "")
    return any(k.replace(" ", "") in lowered for k in _CRISIS_KEYWORDS)