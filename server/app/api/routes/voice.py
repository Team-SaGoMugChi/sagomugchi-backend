from fastapi import APIRouter, UploadFile

from app.models.voice import VoiceAnalysisResult
from app.services.voice_analysis import analyze_voice

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("/voice", response_model=VoiceAnalysisResult)
async def analyze_voice_endpoint(file: UploadFile) -> VoiceAnalysisResult:
    audio_bytes = await file.read()
    return analyze_voice(audio_bytes)
