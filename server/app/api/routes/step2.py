import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.fusion import FeatureDeltaOut, FusionResponse
from app.services.baseline_delta import FeatureDelta, compute_face_delta, compute_voice_delta
from app.services.face_features import extract_face_features
from app.services.fusion import fuse_emotion
from app.services.voice_features import extract_voice_features

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
    text: str = Form(..., description="Step1 STT 결과(또는 Step2 수정본) 원문"),
    voice_file: UploadFile = File(...),
    face_image: UploadFile = File(...),
    baseline_voice: str = Form(
        "{}", description="baseline 음성 맵 (JSON 문자열) — Firestore 연동 전까지 클라이언트가 직접 전달"
    ),
    baseline_face: str = Form("{}", description="baseline 표정 맵 (JSON 문자열)"),
    user_id: str | None = Form(None, description="저장 연동 전까진 미사용. Firestore 연동 시 사용"),
    date: str | None = Form(None, description="yyyy-MM-dd. 저장 연동 전까진 미사용"),
) -> FusionResponse:
    baseline_voice_map = _parse_baseline_map(baseline_voice, "baseline_voice")
    baseline_face_map = _parse_baseline_map(baseline_face, "baseline_face")

    voice_bytes = await voice_file.read()
    face_bytes = await face_image.read()

    voice_features = extract_voice_features(voice_bytes)
    face_features = extract_face_features(face_bytes)

    voice_delta = compute_voice_delta(baseline_voice_map, voice_features)
    face_delta = compute_face_delta(baseline_face_map, face_features)

    result = fuse_emotion(text, voice_delta, face_delta)

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
    )
