"""표정 분석 서비스 — API 응답(FaceAnalysisResult) 조립.

실제 특징 추출은 app/services/face_features.py에 위임한다.
현재는 단일 이미지(프레임 1장) 입력만 지원한다 — 영상 프레임 단위 분석은
baseline/일기 Step1 연동 시점에 확장.
"""

from app.models.face import FaceAnalysisResult
from app.services.face_features import extract_face_features


def analyze_face(image_bytes: bytes) -> FaceAnalysisResult:
    features = extract_face_features(image_bytes)

    return FaceAnalysisResult(
        frame_count=1,
        landmarks_detected=features.landmarks_detected,
        action_units={},  # TODO(Phase 4): eye/mouth/eyebrow 비율 → FACS AU 강도 매핑
        dominant_expression=None,  # TODO(Phase 4): AU 조합 → 표정 라벨 분류
    )
