import cv2
import numpy as np

from app.services.face_features import extract_face_features, extract_features_from_landmarks


class _FakePoint:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


def _build_landmarks(overrides: dict[int, tuple[float, float]], count: int = 478) -> list[_FakePoint]:
    landmarks = [_FakePoint(0.0, 0.0) for _ in range(count)]
    for idx, (x, y) in overrides.items():
        landmarks[idx] = _FakePoint(x, y)
    return landmarks


# 눈/입 크게 뜨고 눈썹 올라간 상태를 흉내낸 좌표
_OPEN_EXPRESSIVE_OVERRIDES = {
    33: (0.30, 0.40),
    160: (0.33, 0.37),
    158: (0.36, 0.37),
    133: (0.39, 0.40),
    153: (0.36, 0.43),
    144: (0.33, 0.43),
    362: (0.61, 0.40),
    385: (0.64, 0.37),
    387: (0.67, 0.37),
    263: (0.70, 0.40),
    373: (0.67, 0.43),
    380: (0.64, 0.43),
    105: (0.345, 0.30),
    334: (0.655, 0.30),
    61: (0.40, 0.65),
    291: (0.62, 0.65),
    13: (0.51, 0.60),
    14: (0.51, 0.72),
}

# 눈/입 감고 눈썹 무표정인 상태를 흉내낸 좌표 (눈 간 거리는 동일하게 유지)
_CLOSED_NEUTRAL_OVERRIDES = {
    33: (0.30, 0.40),
    160: (0.33, 0.399),
    158: (0.36, 0.399),
    133: (0.39, 0.40),
    153: (0.36, 0.401),
    144: (0.33, 0.401),
    362: (0.61, 0.40),
    385: (0.64, 0.399),
    387: (0.67, 0.399),
    263: (0.70, 0.40),
    373: (0.67, 0.401),
    380: (0.64, 0.401),
    105: (0.345, 0.36),
    334: (0.655, 0.36),
    61: (0.45, 0.65),
    291: (0.57, 0.65),
    13: (0.51, 0.648),
    14: (0.51, 0.652),
}


def test_extract_features_from_landmarks_open_vs_closed():
    open_features = extract_features_from_landmarks(_build_landmarks(_OPEN_EXPRESSIVE_OVERRIDES))
    closed_features = extract_features_from_landmarks(_build_landmarks(_CLOSED_NEUTRAL_OVERRIDES))

    assert open_features.landmarks_detected is True
    assert closed_features.landmarks_detected is True

    assert open_features.eye_aspect_ratio > closed_features.eye_aspect_ratio
    assert open_features.mouth_aspect_ratio > closed_features.mouth_aspect_ratio
    assert open_features.mouth_width_ratio > closed_features.mouth_width_ratio
    assert open_features.eyebrow_raise_ratio > closed_features.eyebrow_raise_ratio


def test_extract_face_features_returns_not_detected_for_blank_image():
    blank_image = np.full((240, 320, 3), 128, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", blank_image)
    assert success

    features = extract_face_features(encoded.tobytes())

    assert features.landmarks_detected is False
    assert features.eye_aspect_ratio is None
    assert features.mouth_aspect_ratio is None
    assert features.mouth_width_ratio is None
    assert features.eyebrow_raise_ratio is None
