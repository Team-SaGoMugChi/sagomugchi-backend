"""MediaPipe FaceMesh 기반 저수준 표정 특징 추출 (눈/입 개폐, 눈썹 위치).

baseline 측정과 일기 Step1 표정 분석이 공통으로 쓰는 추출 함수 모음.
API 응답 스키마(app/models/face.py)와는 분리된, 순수 계산 레이어.

여기서 나오는 지표는 FACS Action Unit을 직접 계산한 게 아니라, 랜드마크 좌표로부터
구한 기하학적 근사치(proxy)다 — 예: eye_aspect_ratio↓는 AU45(눈감음)/AU07(눈 조임)과,
mouth_width_ratio↑는 AU12(입꼬리 당김)와, eyebrow_raise_ratio↑는 AU01/AU02(눈썹 올림)와
방향이 같다. 정식 AU 강도(0~5 스케일) 캘리브레이션·표정 라벨 분류는 TODO(Phase 4).
"""

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

# FaceMesh 랜드마크 인덱스 (refine_landmarks=True, 468+iris 10개 기준).
# EAR(eye aspect ratio) 6포인트 서브셋 — 다수의 공개 mediapipe 눈 깜빡임 감지 구현에서
# 쓰이는 인덱스 조합. 순서: [가로축 끝1, 위1, 위2, 가로축 끝2, 아래1, 아래2]
_RIGHT_EYE_IDX = [33, 160, 158, 133, 153, 144]
_LEFT_EYE_IDX = [362, 385, 387, 263, 373, 380]
_LEFT_EYEBROW_IDX = 105
_RIGHT_EYEBROW_IDX = 334
_MOUTH_CORNER_LEFT_IDX = 61
_MOUTH_CORNER_RIGHT_IDX = 291
_MOUTH_TOP_IDX = 13
_MOUTH_BOTTOM_IDX = 14

_face_mesh = mp.solutions.face_mesh.FaceMesh(
    static_image_mode=True,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
)


@dataclass
class FaceFeatures:
    landmarks_detected: bool
    eye_aspect_ratio: float | None  # 눈 개폐 정도(EAR), 좌우 평균 — 낮을수록 감김
    mouth_aspect_ratio: float | None  # 입 개폐 정도(MAR) — 높을수록 크게 벌림
    mouth_width_ratio: float | None  # 입 가로폭 / 눈 간 거리 — 미소 폭 근사
    eyebrow_raise_ratio: float | None  # 눈썹-눈 거리 / 눈 간 거리 — 높을수록 눈썹 올라감


def _landmark_xy(landmarks, idx: int) -> np.ndarray:
    point = landmarks[idx]
    return np.array([point.x, point.y])


def _eye_center(landmarks, eye_idx: list[int]) -> np.ndarray:
    points = np.array([_landmark_xy(landmarks, i) for i in eye_idx])
    return points.mean(axis=0)


def _eye_aspect_ratio(landmarks, eye_idx: list[int]) -> float:
    p1, p2, p3, p4, p5, p6 = (_landmark_xy(landmarks, i) for i in eye_idx)
    vertical = np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)
    horizontal = np.linalg.norm(p1 - p4)
    return float(vertical / (2.0 * horizontal)) if horizontal > 0 else 0.0


def _inter_ocular_distance(landmarks) -> float:
    right_center = _eye_center(landmarks, _RIGHT_EYE_IDX)
    left_center = _eye_center(landmarks, _LEFT_EYE_IDX)
    return float(np.linalg.norm(right_center - left_center))


def _mouth_aspect_ratio(landmarks) -> float:
    top = _landmark_xy(landmarks, _MOUTH_TOP_IDX)
    bottom = _landmark_xy(landmarks, _MOUTH_BOTTOM_IDX)
    left = _landmark_xy(landmarks, _MOUTH_CORNER_LEFT_IDX)
    right = _landmark_xy(landmarks, _MOUTH_CORNER_RIGHT_IDX)
    horizontal = np.linalg.norm(left - right)
    vertical = np.linalg.norm(top - bottom)
    return float(vertical / horizontal) if horizontal > 0 else 0.0


def _mouth_width_ratio(landmarks, inter_ocular: float) -> float:
    left = _landmark_xy(landmarks, _MOUTH_CORNER_LEFT_IDX)
    right = _landmark_xy(landmarks, _MOUTH_CORNER_RIGHT_IDX)
    width = float(np.linalg.norm(left - right))
    return width / inter_ocular if inter_ocular > 0 else 0.0


def _eyebrow_raise_ratio(landmarks, inter_ocular: float) -> float:
    left_gap = np.linalg.norm(_landmark_xy(landmarks, _LEFT_EYEBROW_IDX) - _eye_center(landmarks, _LEFT_EYE_IDX))
    right_gap = np.linalg.norm(_landmark_xy(landmarks, _RIGHT_EYEBROW_IDX) - _eye_center(landmarks, _RIGHT_EYE_IDX))
    avg_gap = float((left_gap + right_gap) / 2.0)
    return avg_gap / inter_ocular if inter_ocular > 0 else 0.0


def extract_features_from_landmarks(landmarks) -> FaceFeatures:
    """랜드마크 시퀀스(인덱스로 .x/.y 접근 가능한 468개+ 포인트)로부터 표정 특징 계산.

    MediaPipe 얼굴 검출과 분리해뒀기 때문에, 실제 이미지 없이도 좌표를 직접 조립해
    단위 테스트할 수 있다.
    """
    inter_ocular = _inter_ocular_distance(landmarks)
    right_ear = _eye_aspect_ratio(landmarks, _RIGHT_EYE_IDX)
    left_ear = _eye_aspect_ratio(landmarks, _LEFT_EYE_IDX)

    return FaceFeatures(
        landmarks_detected=True,
        eye_aspect_ratio=(right_ear + left_ear) / 2.0,
        mouth_aspect_ratio=_mouth_aspect_ratio(landmarks),
        mouth_width_ratio=_mouth_width_ratio(landmarks, inter_ocular),
        eyebrow_raise_ratio=_eyebrow_raise_ratio(landmarks, inter_ocular),
    )


def extract_face_features(image_bytes: bytes) -> FaceFeatures:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        return FaceFeatures(
            landmarks_detected=False,
            eye_aspect_ratio=None,
            mouth_aspect_ratio=None,
            mouth_width_ratio=None,
            eyebrow_raise_ratio=None,
        )

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    result = _face_mesh.process(rgb_image)
    if not result.multi_face_landmarks:
        return FaceFeatures(
            landmarks_detected=False,
            eye_aspect_ratio=None,
            mouth_aspect_ratio=None,
            mouth_width_ratio=None,
            eyebrow_raise_ratio=None,
        )

    landmarks = result.multi_face_landmarks[0].landmark
    return extract_features_from_landmarks(landmarks)
