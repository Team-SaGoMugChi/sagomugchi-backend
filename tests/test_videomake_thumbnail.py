"""대표 장면 썸네일 — 대표 감정의 컷을 가로(16:9)로 한 장 더 그린다. 모든 provider 가짜, 비용 0."""

import asyncio
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.video_job import VideoJobManager, get_video_jobs
from app.videomake.config import Settings
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.registry import build_fake_providers
from app.videomake.stages.storyboard import _StoryboardDraft
from app.videomake.stages.thumbnail import representative_cut

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)


def _payload(cuts):
    """cuts: (mood, 길이, 무음 여부) 목록."""
    payload = fake.demo_storyboard_payload(len(cuts))
    for cut, (mood, seconds, silent) in zip(payload["cuts"], cuts):
        cut.update(mood=mood, duration_seconds=seconds)
        if silent:
            cut["narration"] = ""
    return payload


def _sb(cuts):
    return _StoryboardDraft.model_validate(_payload(cuts)).to_storyboard()


@pytest.mark.parametrize(
    ("cuts", "primary", "expected"),
    [
        # 대표 감정과 같은 컷 중 목소리 있고 긴 컷
        ([("평온", 4, False), ("기쁨", 4, False), ("기쁨", 6, False), ("슬픔", 6, False)], "기쁨", 3),
        # 무음 컷보다 나레이션 컷
        ([("평온", 4, False), ("기쁨", 4, True), ("기쁨", 4, False)], "기쁨", 3),
        # 대표 감정 컷이 없으면 평온이 아닌 컷
        ([("평온", 4, False), ("분노", 6, False), ("평온", 4, False)], "기쁨", 2),
        # 감정 정보가 없어도 평온이 아닌 컷
        ([("평온", 4, False), ("슬픔", 4, False), ("평온", 4, False)], None, 2),
        # 전부 평온이면 가운데 컷
        ([("평온", 4, False), ("평온", 4, False), ("평온", 4, False)], "기쁨", 2),
    ],
)
def test_representative_cut(cuts, primary, expected):
    assert representative_cut(_sb(cuts), primary).index == expected


class _RecordingImage(fake.FakeImage):
    def __init__(self, fail_thumbnail=False):
        self.calls = []
        self.fail_thumbnail = fail_thumbnail

    async def generate(self, *, prompt, dest, aspect_ratio="9:16", **kwargs):
        self.calls.append((dest.name, aspect_ratio, prompt))
        if self.fail_thumbnail and dest.name == "thumbnail_raw.png":
            raise RuntimeError("썸네일 모델 오류")
        return await super().generate(prompt=prompt, dest=dest, aspect_ratio=aspect_ratio, **kwargs)


def _run(tmp_path, image, emotion=None):
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0)
    base = build_fake_providers(settings)
    llm = fake.FakeLLM(3)
    llm.payload = _payload([("평온", 4, False), ("기쁨", 4, False), ("슬픔", 4, False)])
    providers = base.__class__(**{**base.__dict__, "llm": llm, "image": image})
    pipe = Pipeline(providers=providers, job=JobStore(settings.jobs_dir, "thumb"), settings=settings)

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기", emotion=emotion or {}))
        pipe.approve(sb)
        return await pipe.finish(sb)

    return pipe, asyncio.run(run())


def _size(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return tuple(int(v) for v in out.split(","))


def test_thumbnail_is_a_landscape_redraw_of_the_representative_cut(tmp_path):
    image = _RecordingImage()
    pipe, final = _run(tmp_path, image, emotion={"primary": "슬픔"})

    assert final.exists()
    assert pipe.job.thumbnail_path.exists()
    width, height = _size(pipe.job.thumbnail_path)
    assert width == 960 and abs(width / height - 16 / 9) < 0.02
    name, aspect, prompt = next(c for c in image.calls if c[0] == "thumbnail_raw.png")
    assert aspect == "16:9"
    assert "Horizontal 16:9 composition" in prompt
    assert "quietly sad" in prompt  # 대표 감정(슬픔) 컷의 mood
    assert "Third-person observational medium shot" in prompt  # 작은 카드라 인물을 키운다
    assert "fill about half of the frame height" in prompt
    assert "modest portion of the frame" not in prompt


def test_thumbnail_failure_does_not_fail_the_video(tmp_path):
    pipe, final = _run(tmp_path, _RecordingImage(fail_thumbnail=True))

    assert final.exists()
    assert not pipe.job.thumbnail_path.exists()


def test_job_status_and_endpoint_serve_the_thumbnail(tmp_path):
    settings = Settings(_env_file=None, dummy=True, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0,
                        min_cuts=2, min_total_seconds=8)
    manager = VideoJobManager(settings)
    app.dependency_overrides[get_video_jobs] = lambda: manager
    try:
        client = TestClient(app)
        job_id = client.post("/video/jobs", json={"text": "일기", "emotion_keywords": ["기쁨"]}).json()["job_id"]

        status = client.get(f"/video/jobs/{job_id}").json()
        assert status["status"] == "done", status
        assert status["thumbnail_url"] == f"/video/jobs/{job_id}/thumbnail"
        response = client.get(status["thumbnail_url"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert client.get("/video/jobs/없는작업/thumbnail").status_code == 404
    finally:
        app.dependency_overrides.clear()
