from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter

from app.models.diary_interview import (
    InterviewTurnRequest,
    InterviewTurnResponse,
    RefineRequest,
    RefineResponse,
)
from app.services import diary_interview, diary_refine
from app.services.counsel_guardrail import RiskLevel, assess, crisis_reply

router = APIRouter(prefix="/diary", tags=["diary"])


@router.post("/interview/turn", response_model=InterviewTurnResponse)
async def interview_turn(payload: InterviewTurnRequest) -> InterviewTurnResponse:
    # 위기 발화는 상담과 같은 기준으로 LLM에 보내지 않고 축에 맞는 안내로 응답한다.
    risk = assess(payload.user_text)
    if risk.level is RiskLevel.CRISIS:
        return InterviewTurnResponse(reply=crisis_reply(risk), crisis=True)

    turn = await run_in_threadpool(
        diary_interview.next_turn, payload.history, payload.user_text
    )
    return InterviewTurnResponse(
        reply=turn.reply,
        done=turn.done,
        slots=turn.slots,
        missing=turn.missing,
        summary=turn.summary,
    )


@router.post("/interview/refine", response_model=RefineResponse)
async def interview_refine(payload: RefineRequest) -> RefineResponse:
    """대화 전체를 일기 한 편으로 정제한다(보여주기용 — 감정 분석 입력이 아니다)."""
    diary = await run_in_threadpool(diary_refine.refine_diary, payload.messages)
    return RefineResponse(diary=diary)