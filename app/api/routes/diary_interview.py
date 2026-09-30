from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter

from app.models.diary_interview import InterviewTurnRequest, InterviewTurnResponse
from app.services import diary_interview
from app.services.counsel_guardrail import CRISIS_REPLY, is_crisis

router = APIRouter(prefix="/diary", tags=["diary"])


@router.post("/interview/turn", response_model=InterviewTurnResponse)
async def interview_turn(payload: InterviewTurnRequest) -> InterviewTurnResponse:
    # 위기 발화는 상담과 같은 기준으로 LLM에 보내지 않고 정해진 안내로 응답한다.
    if is_crisis(payload.user_text):
        return InterviewTurnResponse(reply=CRISIS_REPLY, crisis=True)

    turn = await run_in_threadpool(
        diary_interview.next_turn, payload.history, payload.user_text
    )
    return InterviewTurnResponse(
        reply=turn.reply, done=turn.done, slots=turn.slots, missing=turn.missing
    )
