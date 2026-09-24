from fastapi import APIRouter

from app.models.counsel import CounselTurnRequest, CounselTurnResponse
from app.services import counsel_context, llm_client
from app.services.counsel_guardrail import CRISIS_REPLY, is_crisis
from app.services.counsel_prompt import build_system_prompt

router = APIRouter(prefix="/counsel", tags=["counsel"])

_FALLBACK = "지금은 연결이 어려워요. 잠시 후 다시 이야기해줄래요?"


@router.post("/turn", response_model=CounselTurnResponse)
async def counsel_turn(payload: CounselTurnRequest) -> CounselTurnResponse:
    # 위기 발화는 LLM에 보내지 않고 정해진 안내로 응답한다.
    if is_crisis(payload.user_text):
        return CounselTurnResponse(reply=CRISIS_REPLY, crisis=True)

    # baseline·감정 분석·일기 요약. 아직 안 넘어오는 값은 더미로 채워진다.
    context = counsel_context.resolve(
        emotions=payload.emotions,
        signals=payload.signals,
        diary_summary=payload.diary_summary,
        recent_themes=payload.recent_themes,
        incongruent=payload.incongruent,
    )

    system_prompt = build_system_prompt(
        persona=payload.persona,
        emotions=context.emotions,
        incongruent=context.incongruent,
        signals=context.signals,
        diary_summary=context.diary_summary,
        recent_themes=context.recent_themes,
    )
    messages = [
        {
            "role": "assistant" if m.speaker == "oddo" else "user",
            "content": m.text,
        }
        for m in payload.history
    ]
    messages.append({"role": "user", "content": payload.user_text})

    try:
        reply = llm_client.chat(system_prompt, messages)
    except Exception:
        # 키 미설정·네트워크 오류 등 — 앱이 멈추지 않도록 폴백.
        reply = _FALLBACK

    return CounselTurnResponse(
        reply=reply or _FALLBACK,
        used_dummy_context=context.used_dummy,
    )
