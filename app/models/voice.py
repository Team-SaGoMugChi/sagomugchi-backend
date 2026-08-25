from pydantic import BaseModel, Field


class VoiceAnalysisResult(BaseModel):
    """librosa 기반 음성 분석 결과 (피치/속도/에너지).

    TODO(Phase 4): app/services/voice_analysis.py 에서 librosa로 실제 계산.
    현재는 스켈레톤이라 placeholder 값을 반환함.
    """

    duration_sec: float = Field(..., description="오디오 길이(초)")
    pitch_hz: float | None = Field(None, description="평균 피치(F0, Hz)")
    speech_rate_wpm: float | None = Field(None, description="발화 속도(분당 단어 수 추정)")
    energy_rms: float | None = Field(None, description="평균 RMS 에너지")
