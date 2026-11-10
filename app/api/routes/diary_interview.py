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
from app.services.counsel_guardrail import RiskAxis, RiskLevel, assess
from app.services.kote_emotion import TextEmotionUnavailable
from app.services.text_emotion import get_text_emotion_classifier

router = APIRouter(prefix="/diary", tags=["diary"])


@router.post("/interview/turn", response_model=InterviewTurnResponse)
async def interview_turn(payload: InterviewTurnRequest) -> InterviewTurnResponse:
    # 일기는 있는 그대로 기록하는 곳이라 위험 발화가 있어도 대화를 멈추거나 기관을 안내하지
    # 않는다. 탄카츄가 공감·걱정하며 이어가고, 감지 결과는 상담 전달 JSON(diary_risk)으로
    # 넘겨 상담에서 다룬다(#123). AI 의존("너밖에 없어")은 걱정할 말이 아니라 평소처럼 잇는다.
    risk = assess(payload.user_text)
    care = risk.level is not RiskLevel.NONE and risk.axis is not RiskAxis.DEPENDENCE

    turn = await run_in_threadpool(
        diary_interview.next_turn, payload.history, payload.user_text, care
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