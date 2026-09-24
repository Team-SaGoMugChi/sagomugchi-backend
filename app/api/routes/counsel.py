from fastapi import APIRouter

from app.models.counsel import (
    CounselReport,
    CounselReportRequest,
    CounselTurnRequest,
    CounselTurnResponse,
)
from app.services import counsel_context, counsel_report, llm_client
from app.services.counsel_guardrail import CRISIS_REPLY, is_crisis
from app.services.counsel_prompt import build_system_prompt

router = APIRouter(prefix="/counsel", tags=["counsel"])

_FALLBACK = "지금은 연결이 어려워요. 잠시 후 다시 이야기해줄래요?"


def _to_openai_messages(history: list) -> list[dict]:
    return [
        {
            "role": "assistant" if m.speaker == "oddo" else "user",
            "content": m.text,
        }
        for m in history
    ]


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
    messages = _to_openai_messages(payload.history)
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


@router.post("/report", response_model=CounselReport)
async def counsel_report_create(payload: CounselReportRequest) -> CounselReport:
    """상담 대화를 읽고 46번 화면에 보여줄 리포트를 만든다.

    LLM 호출이 실패해도 폴백 리포트를 돌려주므로 화면이 비지 않는다.
    """
    report = counsel_report.build(
        messages=_to_openai_messages(payload.messages),
        emotions=payload.emotions,
        diary_summary=payload.diary_summary,
    )
    return CounselReport(**report)