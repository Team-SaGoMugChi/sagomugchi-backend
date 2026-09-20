from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.baseline import BaselineProfile
from app.services.baseline_service import BaselineMeasurementError

client = TestClient(app)


def _submit(**files):
    return client.post("/baseline", data={"user_id": "user-1"}, files=files or {
        "voice_file": ("voice.wav", b"audio", "audio/wav"),
        "face_image": ("face.jpg", b"image", "image/jpeg"),
    })


def test_saves_only_valid_profile(monkeypatch):
    profile = BaselineProfile(user_id="user-1", voice={"pitchMean": 220.0},
                              face={"eyeAspectRatio": 0.28}, measured_at="2026-09-15T00:00:00+00:00")
    build = Mock(return_value=profile)
    save = Mock()
    monkeypatch.setattr("app.api.routes.baseline.build_baseline_profile", build)
    monkeypatch.setattr("app.api.routes.baseline.save_baseline_profile", save)
    response = _submit()
    assert response.status_code == 200
    assert response.json() == profile.model_dump()
    build.assert_called_once_with(user_id="user-1", voice_bytes=b"audio", face_image_bytes=b"image")
    save.assert_called_once_with(profile)


@pytest.mark.parametrize("code", ["invalid_audio", "voice_not_detected", "invalid_face_image", "face_not_detected"])
def test_invalid_measurement_never_overwrites_saved_baseline(monkeypatch, code):
    save = Mock()
    monkeypatch.setattr("app.api.routes.baseline.save_baseline_profile", save)
    monkeypatch.setattr("app.api.routes.baseline.build_baseline_profile",
                        Mock(side_effect=BaselineMeasurementError(code, "다시 측정해주세요.")))
    response = _submit()
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": code, "message": "다시 측정해주세요."}
    save.assert_not_called()


def test_corrupt_recording_returns_422_without_saving(monkeypatch):
    save = Mock()
    monkeypatch.setattr("app.api.routes.baseline.save_baseline_profile", save)
    response = _submit()
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_audio"
    save.assert_not_called()


def test_missing_upload_returns_422_without_saving(monkeypatch):
    save = Mock()
    monkeypatch.setattr("app.api.routes.baseline.save_baseline_profile", save)
    response = _submit(voice_file=("voice.wav", b"audio", "audio/wav"))
    assert response.status_code == 422
    save.assert_not_called()
