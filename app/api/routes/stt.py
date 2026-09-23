from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.stt import SttResponse
from app.services.stt import SttError, transcribe_audio

router = APIRouter(prefix="/stt", tags=["stt"])

# 앱이 "다시 녹음해주세요"를 띄워야 하는 경우만 422, 서버/외부 문제는 5xx로 나눈다.
# 같은 파일로 재시도해도 되는지(5xx) 새로 녹음해야 하는지(422)를 앱이 구분할 수 있어야 한다.
_STATUS_BY_CODE = {
    "invalid_audio": 422,
    "speech_not_recognized": 422,
    "stt_not_configured": 503,
    "stt_unavailable": 502,
}


@router.post("/transcribe", response_model=SttResponse)
async def transcribe(voice_file: UploadFile = File(...)) -> SttResponse:
    """Step1 녹음 → CLOVA Speech → 원문 텍스트.

    파일 필드명 `voice_file`은 앱이 이미 쓰는 이름에 맞춘 것이다
    (프론트 diary_analysis_remote_data_source.dart의 postMultipart filePaths).
    """
    audio_bytes = await voice_file.read()
    try:
        result = await transcribe_audio(audio_bytes, filename=voice_file.filename or "audio.wav")
    except SttError as exc:
        raise HTTPException(
            status_code=_STATUS_BY_CODE.get(exc.code, 502),
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return SttResponse(
        text=result.text,
        confidence=result.confidence,
        duration_ms=result.duration_ms,
        word_count=result.word_count,
    )
