"""Naver CLOVA Speech(STT) 프록시 — 오디오를 받아 텍스트로 변환.

ROADMAP.md(2026-07-29 확정): STT는 Naver CLOVA Speech를 쓰고 **AI 서버가 프록시**한다.
Secret Key를 앱에 넣으면 APK에서 추출돼 남이 우리 도메인으로 과금을 일으킬 수 있고,
키를 교체하면 이미 설치된 앱이 전부 멈춘다. 그래서 클라이언트는 CLOVA를 직접 부르지
않고 오디오를 이 서버에 올리며, CLOVA를 호출하는 건 서버뿐이다. 앱의 speech_to_text
(온디바이스)는 키가 필요 없으므로 오프라인/폴백 경로로만 유지한다.

키는 NCP 콘솔 > CLOVA Speech > Domain에서 Invoke URL과 Secret Key 두 값을 받아
CLOVA_SPEECH_INVOKE_URL / CLOVA_SPEECH_SECRET에 넣는다 (.env.example 참고).

이 모듈만 async다 — CLOVA 응답이 수십 초까지 걸릴 수 있어서, 동기 호출로 두면 그동안
이벤트 루프가 멈춰 서버가 다른 요청을 못 받는다.
"""

import json
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# CLOVA Speech 장문 인식(completion=sync) 파라미터.
#
# diarization(화자 분리)을 명시하지 않으면 200이 아니라 400이 돌아온다:
#   {"result":"ERROR_REQUEST_PARAMETER","message":"speaker detect is off"}
# 쓰지 않더라도 반드시 명시적으로 꺼야 한다. 일기 녹음은 1인 발화라 enable=False.
# (2026-09-21 실제 도메인으로 확인 — tests/test_stt.py가 이 파라미터를 회귀 고정한다)
_RECOGNIZE_PARAMS = {
    "language": "ko-KR",
    "completion": "sync",
    "fullText": True,
    "diarization": {"enable": False},
}


class SttError(Exception):
    """STT 실패. code는 앱이 분기할 수 있게 라우터가 그대로 응답에 담아 내려보낸다."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class SttResult:
    text: str  # 인식된 전체 원문. Step2에서 사용자가 수정할 수 있다
    confidence: float | None  # CLOVA가 보고한 신뢰도(0~1)
    duration_ms: int | None  # 발화 구간 길이(앞뒤 무음 제외)
    word_count: int  # 인식된 단어 수 — 발화 속도(wpm) 계산용 재료


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> SttResult:
    """오디오 바이트를 CLOVA Speech에 보내 인식 결과를 돌려준다.

    실패는 모두 SttError로 통일한다 — 앱이 재녹음을 안내해야 하는 경우(invalid_audio,
    speech_not_recognized)와 서버/외부 문제(stt_not_configured, stt_unavailable)를
    code로 구분할 수 있게 해서, 라우터가 상태 코드를 나눠 매긴다.
    """
    settings = get_settings()
    invoke_url = (settings.clova_speech_invoke_url or "").rstrip("/")
    secret = settings.clova_speech_secret or ""

    if not invoke_url or not secret:
        # 키 없는 팀원의 로컬 환경. 앱 잘못이 아니므로 재녹음을 안내하지 않는다.
        raise SttError("stt_not_configured", "음성 인식 설정이 아직 없어요. 서버 담당자에게 문의해주세요.")
    if not audio_bytes:
        raise SttError("invalid_audio", "음성 파일을 읽을 수 없어요. 다시 녹음해주세요.")

    try:
        async with httpx.AsyncClient(timeout=settings.clova_speech_timeout_sec) as client:
            response = await client.post(
                f"{invoke_url}/recognizer/upload",
                headers={"X-CLOVASPEECH-API-KEY": secret},
                files={
                    "media": (filename, audio_bytes, "audio/wav"),
                    "params": (None, json.dumps(_RECOGNIZE_PARAMS), "application/json"),
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("CLOVA Speech 연결 실패: %s", exc)
        raise SttError("stt_unavailable", "음성 인식 서버에 연결하지 못했어요. 잠시 후 다시 시도해주세요.") from exc

    if response.status_code != 200:
        # 본문에 ERROR_REQUEST_PARAMETER 같은 원인이 들어온다. Secret Key가 섞일 수 있는
        # 헤더는 남기지 않고 본문만, 그것도 서버 로그에만 남긴다.
        logger.warning("CLOVA Speech가 %s 반환: %s", response.status_code, response.text[:500])
        raise SttError("stt_unavailable", "음성 인식에 실패했어요. 잠시 후 다시 시도해주세요.")

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning("CLOVA Speech 응답이 JSON이 아님: %s", response.text[:200])
        raise SttError("stt_unavailable", "음성 인식 응답을 해석하지 못했어요. 잠시 후 다시 시도해주세요.") from exc

    text = (payload.get("text") or "").strip()
    if not text:
        # 200이지만 말소리가 없었던 경우(무음, 잡음만, 너무 짧은 녹음).
        raise SttError("speech_not_recognized", "말소리를 알아듣지 못했어요. 조용한 곳에서 또박또박 다시 말해주세요.")

    return SttResult(
        text=text,
        confidence=_as_float(payload.get("confidence")),
        duration_ms=_speech_duration_ms(payload),
        word_count=_count_words(payload, text),
    )


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _speech_duration_ms(payload: dict) -> int | None:
    """세그먼트 끝 시각의 최대값 = 발화가 끝난 시점(ms).

    오디오 파일 전체 길이가 아니라 CLOVA가 말소리로 판단한 구간의 끝이다. 녹음 앞뒤의
    무음이 빠지므로 발화 속도 계산에는 파일 길이보다 이 값이 맞다.
    """
    ends = [
        segment["end"]
        for segment in payload.get("segments") or []
        if isinstance(segment, dict) and isinstance(segment.get("end"), int)
    ]
    return max(ends) if ends else None


def _count_words(payload: dict, text: str) -> int:
    """segments[].words의 단어 수. words가 없는 응답이면 공백 분리로 대체한다."""
    total = 0
    for segment in payload.get("segments") or []:
        if isinstance(segment, dict) and isinstance(segment.get("words"), list):
            total += len(segment["words"])
    return total or len(text.split())
