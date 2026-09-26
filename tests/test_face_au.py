import hashlib
from contextlib import contextmanager

import pytest

from app.services import face_au
from app.services.face_au import (
    FaceAu,
    FaceAuExtractor,
    FaceAuUnavailable,
    blendshapes_to_au,
    ensure_model,
    summarize_frames,
)

_BLENDSHAPES = {
    "browInnerUp": 0.2,
    "browDownLeft": 0.6,
    "browDownRight": 0.4,
    "mouthSmileLeft": 0.9,
    "mouthSmileRight": 0.7,
    "mouthFrownLeft": 0.0,
    "mouthFrownRight": 0.1,
    "jawOpen": 0.3,  # AU와 무관한 항목은 무시
}


def test_blendshapes_map_to_four_aus_averaging_left_and_right():
    au = blendshapes_to_au(_BLENDSHAPES)

    assert au == pytest.approx({"au1": 0.2, "au4": 0.5, "au12": 0.8, "au15": 0.05})


def test_missing_blendshape_is_a_model_error():
    scores = dict(_BLENDSHAPES)
    del scores["mouthFrownRight"]

    with pytest.raises(FaceAuUnavailable):
        blendshapes_to_au(scores)


def test_summary_uses_only_detected_frames():
    frames = [
        FaceAu(detected=True, au={"au1": 0.1, "au4": 0.2, "au12": 0.6, "au15": 0.0}),
        FaceAu(detected=False, au={}),
        FaceAu(detected=True, au={"au1": 0.3, "au4": 0.2, "au12": 0.2, "au15": 0.0}),
    ]

    summary = summarize_frames(frames)

    assert summary.frame_count == 2
    assert summary.total_frames == 3
    assert summary.mean == pytest.approx({"au1": 0.2, "au4": 0.2, "au12": 0.4, "au15": 0.0})
    # 모집단 표준편차(ddof=0): 두 값의 절반 차이
    assert summary.std == pytest.approx({"au1": 0.1, "au4": 0.0, "au12": 0.2, "au15": 0.0})


def test_summary_without_any_face_is_empty():
    summary = summarize_frames([FaceAu(detected=False, au={})] * 2)

    assert summary.frame_count == 0
    assert summary.total_frames == 2
    assert summary.mean == {}
    assert summary.std == {}


def test_undecodable_image_is_not_detected_without_loading_model(tmp_path):
    extractor = FaceAuExtractor(str(tmp_path / "missing.task"))

    assert extractor.extract(b"not-an-image") == FaceAu(detected=False, au={})
    assert extractor._landmarker is None


def test_existing_model_with_wrong_hash_is_rejected(tmp_path):
    path = tmp_path / "face_landmarker.task"
    path.write_bytes(b"tampered")

    with pytest.raises(FaceAuUnavailable):
        ensure_model(path)


def _fake_stream(payload: bytes):
    class _Response:
        def raise_for_status(self):
            pass

        def iter_bytes(self):
            yield payload

    @contextmanager
    def stream(*args, **kwargs):
        yield _Response()

    return stream


def test_download_is_verified_and_moved_into_place(tmp_path, monkeypatch):
    payload = b"model-bytes"
    monkeypatch.setattr(face_au, "MODEL_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(face_au.httpx, "stream", _fake_stream(payload))
    path = tmp_path / "nested" / "face_landmarker.task"

    assert ensure_model(path) == path
    assert path.read_bytes() == payload
    assert list(path.parent.iterdir()) == [path]  # 임시 .part 파일이 남지 않는다


def test_download_with_wrong_hash_leaves_nothing_behind(tmp_path, monkeypatch):
    monkeypatch.setattr(face_au.httpx, "stream", _fake_stream(b"unexpected"))
    path = tmp_path / "face_landmarker.task"

    with pytest.raises(FaceAuUnavailable):
        ensure_model(path)
    assert list(tmp_path.iterdir()) == []
