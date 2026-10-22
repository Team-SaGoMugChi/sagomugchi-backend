"""렌더 재시도 — 서버 과부하로 실패한 컷은 다시 시도할 때 새로 제출한다. 비용 0."""

import asyncio
import shutil

import pytest

from app.videomake.config import Settings
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.registry import build_fake_providers


def _pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0,
                        min_cuts=1, min_total_seconds=4)
    base = build_fake_providers(settings)
    llm = fake.FakeLLM(2)
    llm.payload = fake.demo_storyboard_payload(2)
    providers = base.__class__(**{**base.__dict__, "llm": llm})
    return Pipeline(providers=providers, job=JobStore(settings.jobs_dir, "retry"), settings=settings)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_failed_render_is_resubmitted_on_retry(tmp_path, monkeypatch):
    """서버 과부하로 실패한 컷은 다시 시도하면 새로 제출된다(실패한 작업만 다시 조회하지 않는다)."""
    from app.videomake.errors import ProviderError
    from app.videomake.models import VideoStatus

    class _FailOnce(fake.FakeVideo):
        def __init__(self):
            super().__init__()
            self.submits = 0

        async def submit(self, **kwargs):
            self.submits += 1
            return await super().submit(**kwargs)

        async def poll(self, handle):
            if self.submits <= 2 and handle.cut_index == 1:
                return VideoStatus(done=True, failed=True, error="high load")
            return await super().poll(handle)

    pipe = _pipeline(tmp_path, monkeypatch)
    video = _FailOnce()
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "video": video})

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        with pytest.raises(ProviderError, match="high load"):
            await pipe.render(sb)
        assert not pipe.job.cut_handle(1).exists()
        await pipe.render(sb)

    asyncio.run(run())
    assert pipe.job.cut_video(1).exists()
    assert video.submits == 3  # 두 컷 + 실패한 컷 1 재제출



@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_safety_filtered_render_is_resubmitted_on_retry(tmp_path, monkeypatch):
    """작업은 끝났지만 영상이 없는 컷(안전 필터)도 핸들을 지워 다시 시도할 때 새로 제출한다."""
    from app.videomake.errors import ProviderError

    class _FilteredOnce(fake.FakeVideo):
        def __init__(self):
            super().__init__()
            self.submits = 0

        async def submit(self, **kwargs):
            self.submits += 1
            return await super().submit(**kwargs)

        async def fetch(self, handle, dest):
            if self.submits <= 2 and handle.cut_index == 1:
                raise ProviderError("컷 1: 생성된 영상이 없다. 안전 필터 사유: blocked")
            return await super().fetch(handle, dest)

    pipe = _pipeline(tmp_path, monkeypatch)
    video = _FilteredOnce()
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "video": video})

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        with pytest.raises(ProviderError, match="안전 필터"):
            await pipe.render(sb)
        assert not pipe.job.cut_handle(1).exists()
        await pipe.render(sb)

    asyncio.run(run())
    assert pipe.job.cut_video(1).exists()
    assert video.submits == 3
