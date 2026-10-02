import json

from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.fusion import FeatureDeltaOut, FusionResponse
from app.services.baseline_contract import (
    BaselineContractError,
    validate_analysis_baseline,
)
from app.services.baseline_delta import FeatureDelta, compute_face_delta, compute_voice_delta
from app.services.analysis_media import (
    AnalysisMediaError,
    AnalysisMediaUnavailable,
    extract_analysis_features,
    extract_daily_multimodal_features,
)
from app.services.fusion import fuse_emotion
from app.services.kote_emotion import MAX_TEXT_LENGTH, TextEmotionUnavailable

router = APIRouter(prefix="/diary", tags=["diary"])


def _parse_baseline_map(raw: str, field_name: str) -> dict[str, float]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be a JSON object string") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a JSON object string")
    return parsed


def _delta_map_to_response(deltas: dict[str, FeatureDelta]) -> dict[str, FeatureDeltaOut]:
    return {
        key: FeatureDeltaOut(
            baseline_value=delta.baseline_value,
            current_value=delta.current_value,
            delta=delta.delta,
            relative_delta=delta.relative_delta,
        )
        for key, delta in deltas.items()
    }


@router.post("/step2/analyze", response_model=FusionResponse)
async def analyze_step2(
    text: str = Form(..., min_length=1, max_length=MAX_TEXT_LENGTH, description="Step1 STT 결과(또는 Step2 수정본) 원문"),
    voice_file: UploadFile = File(...),
    face_image: UploadFile | None = File(None),
    face_images: list[UploadFile] | None = File(None),
    face_timeline: str | None = Form(None),
    baseline_voice: str = Form(
        "{}", description="baseline 음성 맵 (JSON 문자열) — Firestore 연동 전까지 클라이언트가 직접 전달"
    ),
    baseline_face: str = Form("{}", description="baseline 표정 맵 (JSON 문자열)"),
    baseline_feature_version: int = Form(
        0, description="baseline 특징 계약 버전"
    ),
    baseline_measured_at: str = Form(
        "", description="baseline 측정 시각(UTC ISO-8601)"
    ),
    user_id: str | None = Form(None, description="저장 연동 전까진 미사용. Firestore 연동 시 사용"),
    date: str | None = Form(None, description="yyyy-MM-dd. 저장 연동 전까진 미사용"),
) -> FusionResponse:
    if not text.strip():
        raise HTTPException(422, detail="text must not be blank")
    baseline_voice_map = _parse_baseline_map(baseline_voice, "baseline_voice")
    baseline_face_map = _parse_baseline_map(baseline_face, "baseline_face")
    try:
        validate_analysis_baseline(
            feature_version=baseline_feature_version,
            measured_at=baseline_measured_at,
            voice=baseline_voice_map,
            face=baseline_face_map,
        )
    except BaselineContractError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "baseline_remeasurement_required", "message": str(exc)},
        ) from exc

    voice_bytes = await voice_file.read()
    uploads = list(face_images or [])
    if face_image is not None:
        uploads.append(face_image)
    face_bytes = [content for upload in uploads if (content := await upload.read())]

    try:
        voice_features, face_features = extract_analysis_features(
            voice_bytes, face_bytes
        )
    except AnalysisMediaError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    voice_delta = compute_voice_delta(baseline_voice_map, voice_features)
    face_delta = compute_face_delta(baseline_face_map, face_features)

    try:
        timeline_options = (
            {"face_timeline": face_timeline, "voice_features": voice_features}
            if face_timeline is not None else {}
        )
        multimodal = extract_daily_multimodal_features(
            voice_bytes,
            face_bytes,
            baseline_voice_map,
            baseline_face_map,
            **timeline_options,
        )
    except AnalysisMediaError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except AnalysisMediaUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "emotion_analysis_unavailable",
                "message": "표정·음성 분석기를 사용할 수 없어요. 잠시 후 다시 시도해주세요.",
            },
        ) from exc

    try:
        result = await run_in_threadpool(
            fuse_emotion,
            text,
            voice_delta,
            face_delta,
            multimodal.face,
            multimodal.voice,
        )
    except TextEmotionUnavailable as exc:
        raise HTTPException(503, detail={"code": "text_emotion_unavailable", "message": "감정 분석 모델을 사용할 수 없어요. 잠시 후 다시 시도해주세요."}) from exc
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_text", "message": "분석할 텍스트 길이와 내용을 확인해주세요."}) from exc

    # TODO(Firestore 키 확보 후): user_id/date를 써서
    # app.services.step2_repository.save_step2_fusion_result(user_id, date, result) 호출 →
    # users/{uid}/diaries/{date}에 emotionKeywords/emotionIntensity 병합 저장.
    # 함수 자리와 필드 매핑은 step2_repository.py에 이미 문서화해뒀음.

    return FusionResponse(
        emotion_keywords=result.emotion_keywords,
        emotion_scores=result.emotion_scores,
        emotion_intensity=result.emotion_intensity,
        text_emotion_scores=result.text_emotion.scores,
        voice_delta=_delta_map_to_response(voice_delta),
        face_delta=_delta_map_to_response(face_delta),
        signals=result.signals,
        incongruent=result.incongruent,
        incongruence_sources=result.incongruence_sources,
        modalities=result.modalities,
    )
