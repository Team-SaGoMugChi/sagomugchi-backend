from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter, HTTPException

from app.models.diary_interview import (
    AnswerEmotionRequest,
    AnswerEmotionResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
    RefineRequest,
    RefineResponse,
)
from app.services import diary_interview, diary_refine, interview_emotion
from app.services.counsel_guardrail import RiskLevel, assess, crisis_reply
from app.services.kote_emotion import TextEmotionUnavailable
from app.services.text_emotion import get_text_emotion_classifier

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


@router.post("/interview/emotion", response_model=AnswerEmotionResponse)
async def interview_emotion_route(payload: AnswerEmotionRequest) -> AnswerEmotionResponse:
    """답변 하나의 텍스트 감정 — 통화 중 대시보드용. 앱은 실패해도 대화를 계속한다."""
    try:
        result = await run_in_threadpool(
            interview_emotion.analyze_answer, get_text_emotion_classifier(), payload.user_text
        )
    except TextEmotionUnavailable as exc:
        raise HTTPException(
            503,
            detail={"code": "text_emotion_unavailable", "message": "감정 분석 모델을 사용할 수 없어요. 잠시 후 다시 시도해주세요."},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            422, detail={"code": "invalid_text", "message": "분석할 텍스트 길이와 내용을 확인해주세요."}
        ) from exc
    return AnswerEmotionResponse(
        scores=result.scores,
        dominant_emotion=result.dominant_emotion,
        confidence=result.confidence,
        keywords=result.keywords,
    )


@router.post("/interview/refine", response_model=RefineResponse)
async def interview_refine(payload: RefineRequest) -> RefineResponse:
    """대화 전체를 일기 한 편으로 정제한다(보여주기용 — 감정 분석 입력이 아니다)."""
    diary = await run_in_threadpool(diary_refine.refine_diary, payload.messages)
    return RefineResponse(diary=diary)