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


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_quota_limited_cut_is_submitted_when_a_slot_frees(tmp_path, monkeypatch):
    """동시 작업 한도(429)로 제출 못 한 컷은 앞 컷이 끝난 뒤 다시 제출해 한 번에 완성한다."""
    from app.videomake.errors import ProviderError

    class _OneSlot(fake.FakeVideo):
        def __init__(self):
            super().__init__()
            self.running = 0
            self.submits = 0

        async def submit(self, **kwargs):
            if self.running >= 1:
                raise ProviderError("429 RESOURCE_EXHAUSTED long_running_online_prediction_requests_per_base_model")
            self.running += 1
            self.submits += 1
            return await super().submit(**kwargs)

        async def poll(self, handle):
            status = await super().poll(handle)
            if status.done:
                self.running -= 1
            return status

    pipe = _pipeline(tmp_path, monkeypatch)
    video = _OneSlot()
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "video": video})

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        await pipe.render(sb)
        return sb

    sb = asyncio.run(run())
    assert all(pipe.job.cut_video(c.index).exists() for c in sb.cuts)
    assert video.submits == len(sb.cuts)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_cut_with_someone_walking_in_early_is_rendered_once_more(tmp_path, monkeypatch):
    """화면 끝에 낯선 사람이 일찍 들어온 컷은 한 번 다시 만든다(잘라 내면 쓸 길이가 안 남는다)."""
    from app.videomake.providers.base import SeenFrame

    class _CountingVideo(fake.FakeVideo):
        def __init__(self):
            super().__init__()
            self.submits = 0

        async def submit(self, **kwargs):
            self.submits += 1
            return await super().submit(**kwargs)

    class _EarlyIntruder:
        """처음 만든 1번 컷 영상에만 2초부터 화면 끝에 사람이 보인다(첫 장면부터 보이면 그림 탓이라 다시 만들지 않는다)."""

        def __init__(self):
            self.flagged = False

        async def look(self, *, image, place=None, cast=None):
            edge = "check_edge_02" in image.name and "/cuts/01/" in str(image)
            hit = edge and not self.flagged
            if hit:
                self.flagged = True
            return SeenFrame(people=[], looks_at_camera=False, cut_off_person=hit)

    pipe = _pipeline(tmp_path, monkeypatch)
    video = _CountingVideo()
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "video": video, "look": _EarlyIntruder()})

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        await pipe.render(sb)
        return sb

    sb = asyncio.run(run())
    assert all(pipe.job.cut_video(c.index).exists() for c in sb.cuts)
    assert video.submits == len(sb.cuts) + 1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_status_check_that_never_answers_does_not_freeze_the_render(tmp_path, monkeypatch):
    """응답 없는 진행 상태 조회 하나가 렌더 전체를 멈추지 않는다(제한 시간 뒤 다시 묻는다)."""
    from app.videomake.stages import video_render

    class _HangOnce(fake.FakeVideo):
        def __init__(self):
            super().__init__()
            self.hung = False

        async def poll(self, handle):
            if not self.hung:
                self.hung = True
                await asyncio.sleep(3600)
            return await super().poll(handle)

    monkeypatch.setattr(video_render, "CALL_TIMEOUT_SECONDS", 0.2)
    pipe = _pipeline(tmp_path, monkeypatch)
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "video": _HangOnce()})

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        await asyncio.wait_for(pipe.render(sb), 30)
        return sb

    sb = asyncio.run(run())
    assert all(pipe.job.cut_video(c.index).exists() for c in sb.cuts)


def test_a_call_that_never_answers_is_asked_again():
    """응답 없는 요청은 제한 시간 뒤 다시 묻는다(영상 만들기가 7시간 멈췄다)."""
    from app.videomake.providers.base import retry_on_rate_limit

    calls = []

    async def call():
        calls.append(1)
        if len(calls) == 1:
            await asyncio.sleep(3600)
        return "ok"

    assert asyncio.run(retry_on_rate_limit(call, what="검사", timeout=0.1)) == "ok"
    assert len(calls) == 2
