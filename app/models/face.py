from pydantic import BaseModel, Field


class FaceAnalysisResult(BaseModel):
    """MediaPipe 기반 표정 분석 결과 (FACS AU / 랜드마크 요약).

    TODO(Phase 4): app/services/face_analysis.py 에서 MediaPipe로 실제 계산.
    현재는 스켈레톤이라 placeholder 값을 반환함.
    """

    frame_count: int = Field(..., description="분석에 사용된 프레임 수")
    landmarks_detected: bool = Field(..., description="얼굴 랜드마크 검출 여부")
    action_units: dict[str, float] = Field(
        default_factory=dict, description="FACS Action Unit별 강도 (예: {'AU12': 0.4})"
    )
    dominant_expression: str | None = Field(None, description="추정 대표 표정 라벨")
