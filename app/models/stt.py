from pydantic import BaseModel, Field


class SttResponse(BaseModel):
    """`POST /stt/transcribe` 응답 — 일기 Step1 말하기의 STT 결과.

    `text`는 Step2 확인하기 화면에서 사용자가 수정할 원문이다(FIRESTORE_SCHEMA.md의
    `transcript` 필드에 대응). `duration_ms`/`word_count`는 발화 속도(wpm) 계산 재료로
    같이 내려보내지만, 계산 자체는 아직 붙이지 않았다 — baseline의 `speechRate`가
    음절/초 기준이라 단위를 맞추는 작업이 별도로 필요하다.
    """

    text: str = Field(..., description="인식된 원문. Step2에서 사용자가 수정할 수 있다")
    confidence: float | None = Field(None, description="CLOVA가 보고한 인식 신뢰도(0~1)")
    duration_ms: int | None = Field(None, description="발화 구간 길이(ms). 녹음 앞뒤 무음은 제외")
    word_count: int = Field(..., description="인식된 단어 수. 발화 속도 계산용")
