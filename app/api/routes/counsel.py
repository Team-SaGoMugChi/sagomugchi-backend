from fastapi import APIRouter

from app.models.counsel import CounselTurnRequest, CounselTurnResponse

router = APIRouter(prefix="/counsel", tags=["counsel"])


@router.post("/turn", response_model=CounselTurnResponse)
async def counsel_turn(payload: CounselTurnRequest) -> CounselTurnResponse:
    # TODO: LLM 붙이기 전까지 고정 답변
    return CounselTurnResponse(reply=f"'{payload.user_text}'라고 하셨군요. 조금 더 이야기해줄래요?")