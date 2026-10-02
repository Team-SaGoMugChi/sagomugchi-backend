from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter

from app.models.diary_handoff import HandoffRequest, HandoffResponse
from app.services import diary_handoff

router = APIRouter(prefix="/diary", tags=["diary"])


@router.post("/handoff", response_model=HandoffResponse)
async def build_handoff(payload: HandoffRequest) -> HandoffResponse:
    """일기 기록이 끝난 뒤 영상·상담 파트에 넘길 JSON 두 개를 만든다.

    저장은 앱이 사용자 권한으로 Firestore `users/{uid}/handoffs/{date}`에 한다 — 서버는
    사용자를 확인하지 않으므로 대신 쓰지 않는다.
    """
    video, counsel = await run_in_threadpool(diary_handoff.build_handoff, payload)
    return HandoffResponse(video=video, counsel=counsel)
