from fastapi import APIRouter

from app.core.config import get_settings

from app.models.counsel import (
    CbtTurnState,
    CounselReport,
    CounselReportRequest,
    CounselTurnRequest,
    CounselTurnResponse,
)
from app.services import (
    counsel_cbt,
    counsel_context,
    counsel_output_check,
    counsel_report,
    counsel_risk_judge,
    llm_client,
)
from app.services.counsel_guardrail import (
    RiskLevel,
    assess,
    caution_guide,
    crisis_reply,
)
from app.services.counsel_prompt import build_system_prompt

router = APIRouter(prefix="/counsel", tags=["counsel"])

_FALLBACK = "지금은 연결이 어려워요. 잠시 후 다시 이야기해줄래요?"

# CBT 단계형은 JSON(reply + extracted)으로 받아서 일반 턴보다 길다.
_CBT_MAX_TOKENS = 600


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
    # 위험 축·단계 판정 (기준: docs/CRISIS_POLICY.md).
    # CRISIS는 LLM에 보내지 않고 축에 맞는 안내(연락처)로 응답한다.
    # COUNSEL_LLM_JUDGE=true면 규칙이 놓친 바꿔 말하기를 LLM이 한 번 더 본다.
    risk = (
        counsel_risk_judge.assess_hybrid(payload.user_text)
        if get_settings().counsel_llm_judge
        else assess(payload.user_text)
    )
    risk_axis = risk.axis.value if risk.axis else None

    # CBT 단계형이면 이번 턴의 단계를 정한다. 위기·오류 때는 단계를 그대로 돌려준다.
    cbt = payload.cbt
    stage = counsel_cbt.resolve_stage(cbt.stage, cbt.last_mission) if cbt else None
    unchanged = (
        CbtTurnState(stage=stage, stage_turn=cbt.stage_turn) if cbt else None
    )

    if risk.level is RiskLevel.CRISIS:
        return CounselTurnResponse(
            reply=crisis_reply(risk), crisis=True, risk_axis=risk_axis, cbt=unchanged
        )

    # baseline·감정 분석·일기 요약. 로컬에서 더미 옵션을 명시적으로 켠
    # 경우에만 누락된 값을 예시 데이터로 채운다.
    context = counsel_context.resolve(
        emotions=payload.emotions,
        signals=payload.signals,
        diary_summary=payload.diary_summary,
        recent_themes=payload.recent_themes,
        incongruent=payload.incongruent,
    )

    system_prompt = build_system_prompt(
        persona=payload.persona.model_dump() if payload.persona else None,
        psych_profile=(
            payload.psych_profile.model_dump() if payload.psych_profile else None
        ),
        emotions=context.emotions,
        incongruent=context.incongruent,
        signals=context.signals,
        diary_summary=context.diary_summary,
        recent_themes=context.recent_themes,
        # 일기 대화에서 사용자가 직접 말한 사실 — 더미로 채우지 않는다.
        slots=payload.slots,
        emotion_arc=payload.emotion_arc,
    )
    # CAUTION은 상담을 멈추지 않고, 상담봇이 맥락을 보고 한 번 더 확인하게 한다.
    if risk.level is RiskLevel.CAUTION:
        system_prompt += caution_guide(risk)
    if cbt:
        system_prompt += counsel_cbt.build_cbt_prompt(
            stage, style=cbt.style, last_mission=cbt.last_mission
        )

    messages = _to_openai_messages(payload.history)
    messages.append({"role": "user", "content": payload.user_text})

    def ask(prompt: str) -> counsel_cbt.CbtOutput:
        """일반 턴은 답변 문자열, CBT 턴은 JSON을 읽어 같은 모양으로 맞춘다."""
        if not cbt:
            return counsel_cbt.CbtOutput(reply=llm_client.chat(prompt, messages))
        raw = llm_client.chat(
            prompt, messages, json_mode=True, max_tokens=_CBT_MAX_TOKENS
        )
        return counsel_cbt.parse_output(raw)

    try:
        output = ask(system_prompt)
    except Exception:
        # 키 미설정·네트워크 오류 등 — 앱이 멈추지 않도록 폴백.
        return CounselTurnResponse(
            reply=_FALLBACK,
            risk_axis=risk_axis,
            used_dummy_context=context.used_dummy,
            cbt=unchanged,
        )

    # 응답 검증 레이어 — 보내기 전에 규칙 위반을 검사하고, 어기면 한 번 다시 쓴다.
    # 다시 쓸 때는 reply만 바꾸고, 단계 판단(advance·extracted)은 1차 응답을 따른다.
    checked = counsel_output_check.verify(
        output.reply or _FALLBACK,
        regenerate=lambda feedback: ask(system_prompt + feedback).reply,
        user_texts=[m.text for m in payload.history if m.speaker == "user"]
        + [payload.user_text],
        has_recent_themes=bool(context.recent_themes),
    )

    state = None
    if cbt:
        # 안전 문장으로 대체됐거나 답이 비었으면 단계를 넘기지 않는다.
        if checked.fallback or not output.reply:
            state = unchanged
        else:
            next_stage, next_turn, done = counsel_cbt.next_state(
                stage, cbt.stage_turn, output.advance
            )
            state = CbtTurnState(
                stage=next_stage,
                stage_turn=next_turn,
                extracted=output.extracted,
                done=done,
            )

    return CounselTurnResponse(
        reply=checked.reply,
        risk_axis=risk_axis,
        used_dummy_context=context.used_dummy,
        cbt=state,
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
        slots=payload.slots,
    )
    return CounselReport(**report)