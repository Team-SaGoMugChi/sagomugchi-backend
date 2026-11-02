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


class _BlockUntilWide(fake.FakeVideo):
    """컷 1을 그림이 전신이 될 때까지 안전 필터로 거절한다(실측 메시지 그대로)."""

    def __init__(self, sb_of):
        super().__init__()
        self.sb_of = sb_of
        self.submitted = []

    async def submit(self, **kwargs):
        self.submitted.append(kwargs["cut_index"])
        return await super().submit(**kwargs)

    async def poll(self, handle):
        from app.videomake.models import VideoStatus

        if handle.cut_index == 1 and self.sb_of().cut(1).camera_distance == "medium":
            return VideoStatus(done=True, failed=True, error="{'code': 3, 'message': \"Veo could not generate videos "
                               "because the input image violates Vertex AI's usage guidelines. Support codes: 15236754\"}")
        return await super().poll(handle)


def _blocked_pipeline(tmp_path, monkeypatch):
    pipe = _pipeline(tmp_path, monkeypatch)
    holder = {}
    video = _BlockUntilWide(lambda: holder["sb"])
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "video": video})
    return pipe, video, holder


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_blocked_cut_is_redrawn_wider_and_only_it_is_resubmitted(tmp_path, monkeypatch):
    pipe, video, holder = _blocked_pipeline(tmp_path, monkeypatch)

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        sb.cut(1).camera_distance = "medium"
        holder["sb"] = sb
        pipe.approve(sb)
        await pipe.render(sb, force=True, redraw_blocked=True)
        return sb

    sb = asyncio.run(run())
    assert video.submitted == [1, 2, 1]  # 이미 받은 컷 2는 force여도 다시 과금하지 않는다
    assert sb.cut(1).camera_distance == "full" and "head to toe" in sb.cut(1).image_prompt
    assert pipe.job.load_storyboard().cut(1).camera_distance == "full"  # 이어 받아도 같은 구도
    assert pipe.job.cut_video(1).exists() and pipe.job.cut_video(2).exists()
    assert 1 in pipe.job.approved_cuts()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_blocked_cut_is_not_auto_approved_unless_asked(tmp_path, monkeypatch):
    """사람이 검수하는 흐름: 승인 안 한 그림으로 영상을 만들면 안 되니 거절을 그대로 알린다."""
    from app.videomake.errors import VideoBlocked

    pipe, video, holder = _blocked_pipeline(tmp_path, monkeypatch)

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        sb.cut(1).camera_distance = "medium"
        holder["sb"] = sb
        pipe.approve(sb)
        with pytest.raises(VideoBlocked) as err:
            await pipe.render(sb)
        return sb, err.value

    sb, exc = asyncio.run(run())
    assert exc.cuts == {1} and sb.cut(1).camera_distance == "medium"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_redraws_stop_after_the_limit(tmp_path, monkeypatch):
    from app.videomake.errors import VideoBlocked
    from app.videomake.models import VideoStatus

    pipe, video, holder = _blocked_pipeline(tmp_path, monkeypatch)
    original = fake.FakeVideo.poll

    async def always_block(handle):
        if handle.cut_index == 1:
            return VideoStatus(done=True, failed=True, error="violates usage guidelines")
        return await original(video, handle)

    video.poll = always_block

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        with pytest.raises(VideoBlocked):
            await pipe.render(sb, redraw_blocked=True)

    asyncio.run(run())
    assert video.submitted.count(1) == 3  # 처음 + 다시 그려서 2번
