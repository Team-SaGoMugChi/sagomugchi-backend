"""scripts/video_replay — 같은 일기로 영상만 다시 돌리기. 모든 provider가 가짜라 비용 0."""

import asyncio
import shutil

import pytest

from app.videomake.config import Settings
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.openai_llm import OpenAILLMProvider
from app.videomake.providers.registry import build_fake_providers
from scripts import video_replay

DIARY = DiaryInput(
    text="아침 회의에서 지적을 받아 속상했다. 저녁에 친구와 통화하며 나아졌다.",
    emotion={"primary": "상처"},
    handoff={"schema": "oddo.diary_emotion.v1", "diary": {"summary": "속상했다가 나아졌다"}},
)


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)


def _settings(tmp_path) -> Settings:
    return Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0)


def _saved_job(settings) -> JobStore:
    job = JobStore(settings.jobs_dir, "app-job")
    job.input_path.write_text(DIARY.model_dump_json(), encoding="utf-8")
    return job


def _pipe(settings, name="t") -> Pipeline:
    return Pipeline(
        providers=build_fake_providers(settings),
        job=video_replay.new_job(settings.jobs_dir, name),
        settings=settings,
    )


@pytest.mark.parametrize("source", ["id", "dir", "file"])
def test_input_loads_from_job_id_folder_or_file(tmp_path, source):
    settings = _settings(tmp_path)
    job = _saved_job(settings)
    arg = {"id": "app-job", "dir": str(job.dir), "file": str(job.input_path)}[source]

    assert video_replay.load_input(arg, settings.jobs_dir) == DIARY


def test_missing_input_exits_with_message(tmp_path):
    with pytest.raises(SystemExit, match="--list"):
        video_replay.load_input("없는작업", tmp_path)


def test_storyboard_only_writes_new_job_and_keeps_original(tmp_path):
    settings = _settings(tmp_path)
    original = _saved_job(settings)
    pipe = _pipe(settings)

    sb = asyncio.run(video_replay.replay(DIARY, pipe=pipe, until="storyboard"))

    assert pipe.job.dir.name.startswith("replay-") and pipe.job.dir.name.endswith("-t")
    assert pipe.job.storyboard_path.exists()
    assert not pipe.job.character_sheet_path.exists()
    assert DiaryInput.model_validate_json(pipe.job.input_path.read_text()) == DIARY
    assert not original.storyboard_path.exists()
    summary = video_replay.summary(sb, pipe.job)
    assert f"컷 {len(sb.cuts)}개" in summary and f"합계 {sb.total_seconds}초" in summary


def test_declined_render_stops_before_paid_stage(tmp_path):
    settings = _settings(tmp_path)
    pipe = _pipe(settings)

    with pytest.raises(SystemExit, match="취소"):
        asyncio.run(
            video_replay.replay(DIARY, pipe=pipe, until="video", confirm=lambda est, limit: False)
        )

    assert pipe.job.cut_image(1).exists()
    assert not pipe.job.cut_video(1).exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_video_until_end_makes_final_mp4(tmp_path):
    settings = _settings(tmp_path)
    pipe = _pipe(settings)

    asyncio.run(
        video_replay.replay(DIARY, pipe=pipe, until="video", confirm=lambda est, limit: True)
    )

    assert pipe.job.final_path.exists()

    sb = pipe.job.load_storyboard()
    copied = video_replay.save_copy(sb, pipe.job, tmp_path / "바탕화면")
    assert copied.name == f"{pipe.job.dir.name}_{len(sb.cuts)}컷_{sb.total_seconds}초.mp4"
    assert copied.stat().st_size == pipe.job.final_path.stat().st_size
    assert "합계" in copied.with_suffix(".txt").read_text(encoding="utf-8")


def test_dummy_media_keeps_real_llm(tmp_path):
    settings = Settings(_env_file=None, jobs_dir=tmp_path, llm_provider="openai", openai_api_key="sk-test")

    providers = video_replay.build_replay_providers(settings, media="dummy")

    assert isinstance(providers.llm, OpenAILLMProvider)
    assert isinstance(providers.video, fake.FakeVideo)
    assert providers.client is None
