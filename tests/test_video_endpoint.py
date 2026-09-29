"""`/video/jobs` 엔드포인트. 더미 provider로 돌려 API 비용 0.

TestClient는 BackgroundTasks를 응답 직후 같은 요청 안에서 끝까지 실행한다.
그래서 POST가 돌아오면 작업은 이미 끝나 있다.
"""

import shutil

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.video import VideoJobRequest
from app.services.video_job import VideoJobManager, get_video_jobs, to_diary_input
from app.videomake.config import Settings
from app.videomake.providers import fake

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")

client = TestClient(app)

BODY = {
    "text": "오늘 회의에서 의견을 말했는데 팀장님이 바로 다른 얘기로 넘어갔다.",
    "emotion_keywords": ["슬픔", "분노"],
    "emotion_scores": {"슬픔": 62.0, "분노": 21.0},
    "emotion_intensity": 58,
}


def _manager(tmp_path, **overrides) -> VideoJobManager:
    settings = Settings(
        dummy=True,
        jobs_dir=tmp_path / "jobs",
        n_cuts=2,
        cut_duration_seconds=4,
        poll_interval_seconds=0.0,
        **overrides,
    )
    return VideoJobManager(settings)


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)
    manager = _manager(tmp_path)
    app.dependency_overrides[get_video_jobs] = lambda: manager
    yield manager
    app.dependency_overrides.clear()


def test_step2_result_maps_to_videomake_emotion():
    diary = to_diary_input(VideoJobRequest(**BODY))
    assert diary.emotion == {
        "primary": "슬픔",
        "secondary": ["분노"],
        "intensity": 0.58,
        "scores": {"슬픔": 62.0, "분노": 21.0},
    }


def test_missing_emotion_is_omitted():
    diary = to_diary_input(VideoJobRequest(text="그냥 평범한 하루였다."))
    assert diary.emotion == {}


def test_blank_text_is_rejected(jobs):
    response = client.post("/video/jobs", json={"text": "   "})
    assert response.status_code == 422


@needs_ffmpeg
def test_job_runs_to_done_and_serves_mp4(jobs):
    created = client.post("/video/jobs", json=BODY)
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    status = client.get(f"/video/jobs/{job_id}").json()
    assert status["status"] == "done", status
    assert status["progress"] == 1.0
    assert status["video_url"] == f"/video/jobs/{job_id}/file"

    video = client.get(status["video_url"])
    assert video.status_code == 200
    assert video.headers["content-type"] == "video/mp4"
    assert len(video.content) > 1000


@needs_ffmpeg
def test_budget_exceeded_fails_without_rendering(tmp_path, monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)
    # 더미는 단가 0이라 상한을 음수로 둬야 초과가 된다.
    manager = _manager(tmp_path, max_cost_usd="-1")
    app.dependency_overrides[get_video_jobs] = lambda: manager
    try:
        job_id = client.post("/video/jobs", json=BODY).json()["job_id"]
        status = client.get(f"/video/jobs/{job_id}").json()
    finally:
        app.dependency_overrides.clear()

    assert status["status"] == "failed"
    assert "비용 상한" in status["error"]
    assert status["video_url"] is None
    assert client.get(f"/video/jobs/{job_id}/file").status_code == 404


def test_unknown_job_is_404(jobs):
    response = client.get("/video/jobs/nope")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "job_not_found"


def test_progress_follows_stage_outputs(tmp_path):
    manager = _manager(tmp_path)
    job_id = manager.create()
    status = manager.status(job_id)
    assert (status.status, status.stage, status.progress) == ("running", "storyboard", 0.0)
