"""MediaPipe FaceLandmarker blendshapes → 논문 표 1의 FACS AU 4종 (AU1·AU4·AU12·AU15).

face_features.py(FaceMesh 좌표로 만든 눈/입 비율)를 대체하기 위한 추출 레이어다.
FaceLandmarker는 표정 점수 52개(blendshapes, 0~1)를 직접 주고, 그중 논문이 계측하는
AU와 같은 움직임을 가리키는 항목이 있다:

    AU1  눈썹 안쪽 올림  browInnerUp
    AU4  눈썹 찡그림     browDownLeft/Right 평균
    AU12 입꼬리 올림     mouthSmileLeft/Right 평균
    AU15 입꼬리 내림     mouthFrownLeft/Right 평균

blendshape 점수는 정식 FACS 강도(0~5) 캘리브레이션이 아니라 같은 방향의 근사치다.
또 사람마다 기본 얼굴이 달라 절대값을 그대로 쓰면 틀린다(공식 샘플의 웃는 얼굴에서도
browDown이 0.8대로 나온다) — 반드시 baseline 대비 변화로 비교할 것.

여러 프레임을 받아 AU별 평균·표준편차를 내는 [summarize_frames]까지만 여기서 한다.
baseline 저장 키(feature_maps)와 fusion 연결은 팀 합의 후 별도로 붙인다.
"""

import hashlib
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from threading import Lock

import cv2
import httpx
import numpy as np

from app.core.config import get_settings

# 공식 모델(float16, v1). 파일이 바뀌면 blendshape 값도 달라지므로 URL과 해시를 고정한다.
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"

AU_KEYS = ("au1", "au4", "au12", "au15")

# 좌우가 나뉜 항목은 평균낸다 — 한쪽만 움직이는 표정보다 얼굴 전체의 방향을 본다.
_AU_BLENDSHAPES: dict[str, tuple[str, ...]] = {
    "au1": ("browInnerUp",),
    "au4": ("browDownLeft", "browDownRight"),
    "au12": ("mouthSmileLeft", "mouthSmileRight"),
    "au15": ("mouthFrownLeft", "mouthFrownRight"),
}


class FaceAuUnavailable(RuntimeError):
    """모델 다운로드·검증·로딩 실패. 조용히 옛 방식으로 대체하지 않는다."""


@dataclass
class FaceAu:
    """프레임 1장의 결과. 얼굴을 못 찾으면 detected=False, au는 빈 dict."""

    detected: bool
    au: dict[str, float]


@dataclass
class FaceAuSummary:
    """여러 프레임의 AU별 평균·표준편차. 표준편차는 모집단 기준(ddof=0) — f0Std와 같은 규칙."""

    frame_count: int  # 얼굴이 검출된 프레임 수 — 평균·표준편차 계산에 쓰인 수
    total_frames: int  # 받은 프레임 수(검출 실패 포함)
    mean: dict[str, float]
    std: dict[str, float]


def blendshapes_to_au(scores: Mapping[str, float]) -> dict[str, float]:
    """blendshape 이름→점수 맵에서 AU 4종을 뽑는다. 필요한 항목이 빠지면 모델 이상으로 본다."""
    missing = {name for names in _AU_BLENDSHAPES.values() for name in names} - scores.keys()
    if missing:
        raise FaceAuUnavailable(f"Missing blendshapes: {sorted(missing)}")
    return {au: sum(scores[name] for name in names) / len(names) for au, names in _AU_BLENDSHAPES.items()}


def summarize_frames(frames: Sequence[FaceAu]) -> FaceAuSummary:
    """검출된 프레임만으로 AU별 평균·표준편차를 낸다. 하나도 없으면 빈 dict."""
    detected = [frame.au for frame in frames if frame.detected]
    if not detected:
        return FaceAuSummary(frame_count=0, total_frames=len(frames), mean={}, std={})

    mean = {key: float(np.mean([au[key] for au in detected])) for key in AU_KEYS}
    std = {key: float(np.std([au[key] for au in detected])) for key in AU_KEYS}
    return FaceAuSummary(frame_count=len(detected), total_frames=len(frames), mean=mean, std=std)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model(path: Path) -> Path:
    """모델 파일이 없으면 받아오고, 해시가 다르면 쓰지 않는다(첫 호출에만 네트워크 사용)."""
    if path.exists():
        if _sha256(path) != MODEL_SHA256:
            raise FaceAuUnavailable(f"{path} does not match the pinned face landmarker model")
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".part")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as file, httpx.stream("GET", MODEL_URL, timeout=60.0, follow_redirects=True) as res:
            res.raise_for_status()
            for chunk in res.iter_bytes():
                file.write(chunk)
        if _sha256(tmp) != MODEL_SHA256:
            raise FaceAuUnavailable("Downloaded face landmarker model hash mismatch")
        # 받는 도중 끊겨도 반쪽 파일이 정식 경로에 남지 않도록 다 받은 뒤 옮긴다.
        tmp.replace(path)
    except httpx.HTTPError as exc:
        raise FaceAuUnavailable("Could not download face landmarker model") from exc
    finally:
        tmp.unlink(missing_ok=True)
    return path


class FaceAuExtractor:
    """이미지 1장 → [FaceAu]. 모델은 첫 호출 때 한 번만 올린다(KOTE와 같은 지연 로딩)."""

    def __init__(self, model_path: str) -> None:
        self.model_path = Path(model_path)
        self._landmarker = None
        # MediaPipe landmarker는 동시 호출에 안전하지 않아 로딩과 추론을 직렬화한다.
        self._lock = Lock()

    def _load(self):
        if self._landmarker is None:
            try:
                from mediapipe.tasks.python import BaseOptions, vision

                options = vision.FaceLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=str(ensure_model(self.model_path))),
                    running_mode=vision.RunningMode.IMAGE,
                    num_faces=1,
                    output_face_blendshapes=True,
                )
                self._landmarker = vision.FaceLandmarker.create_from_options(options)
            except FaceAuUnavailable:
                raise
            except Exception as exc:
                raise FaceAuUnavailable("Face landmarker could not be loaded") from exc
        return self._landmarker

    def extract(self, image_bytes: bytes) -> FaceAu:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return FaceAu(detected=False, au={})

        import mediapipe as mp

        rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        with self._lock:
            result = self._load().detect(rgb)
        if not result.face_blendshapes:
            return FaceAu(detected=False, au={})

        scores = {c.category_name: c.score for c in result.face_blendshapes[0]}
        au = blendshapes_to_au(scores)
        if not all(math.isfinite(value) for value in au.values()):
            raise FaceAuUnavailable("Face landmarker returned non-finite scores")
        return FaceAu(detected=True, au=au)

    def extract_frames(self, images: Sequence[bytes]) -> FaceAuSummary:
        return summarize_frames([self.extract(image) for image in images])


@lru_cache(maxsize=1)
def get_face_au_extractor() -> FaceAuExtractor:
    return FaceAuExtractor(get_settings().face_landmarker_model_path)
