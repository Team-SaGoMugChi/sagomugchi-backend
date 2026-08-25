"""음성 분석 서비스 — API 응답(VoiceAnalysisResult) 조립.

실제 특징 추출은 app/services/voice_features.py에 위임한다.
발화 속도는 voice_features가 음절/초(DSP 근사치)로 추정하지만, 기존 API 필드인
speech_rate_wpm(분당 단어 수)은 STT 텍스트가 있어야 정확히 계산되어 Phase 5까지 None.
"""

from app.models.voice import VoiceAnalysisResult
from app.services.voice_features import extract_voice_features


def analyze_voice(audio_bytes: bytes) -> VoiceAnalysisResult:
    features = extract_voice_features(audio_bytes)

    return VoiceAnalysisResult(
        duration_sec=features.duration_sec,
        pitch_hz=features.f0_mean_hz,
        speech_rate_wpm=None,  # TODO(Phase 5): STT 텍스트 길이 / duration으로 계산
        energy_rms=features.rms_mean,
    )
