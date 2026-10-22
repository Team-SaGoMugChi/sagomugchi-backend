"""evolink 영상 provider — 모델마다 다른 요청 칸, 길이 맞추기, 대사 컷 라우팅. 네트워크·비용 0."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.videomake.config import Settings
from app.videomake.errors import ProviderError
from app.videomake.models import VideoHandle, VideoResult, VideoStatus
from app.videomake.providers.evolink_video import (
    MODELS,
    EvolinkVideoProvider,
    build_body,
    request_duration,
)
from app.videomake.providers.routing_video import RoutingVideoProvider


class _Host:
    def __init__(self):
        self.keys = []

    async def url_for(self, path, key):
        self.keys.append(key)
        return f"https://img.example/{key}"


def _body(model, seconds=4, audio=True):
    return build_body(model, MODELS[model], prompt="She sips coffee.", image_url="https://img/x.png",
                      negative_prompt="subtitles, text", aspect_ratio="9:16",
                      duration_seconds=seconds, generate_audio=audio)


def test_duration_rounds_up_to_what_the_model_supports():
    assert request_duration(MODELS["seedance-2.0-fast-image-to-video"], 4) == 4
    assert request_duration(MODELS["MiniMax-Hailuo-2.3-Fast"], 4) == 6
    assert request_duration(MODELS["MiniMax-Hailuo-2.3-Fast"], 8) == 10
    assert request_duration(MODELS["wan2.5-image-to-video"], 6) == 10
    assert request_duration(MODELS["minimax-h3-max-turbo-image-to-video"], 4) == 5


def test_each_model_gets_its_own_field_names():
    seed = _body("seedance-2.0-fast-image-to-video")
    assert seed["image_urls"] == ["https://img/x.png"] and seed["generate_audio"] is True
    assert seed["aspect_ratio"] == "9:16" and "Avoid: subtitles, text" in seed["prompt"]

    kling = _body("kling-v3-image-to-video", audio=False)
    assert kling["image_start"] == "https://img/x.png" and kling["sound"] == "off"
    assert kling["negative_prompt"] == "subtitles, text" and "Avoid:" not in kling["prompt"]

    hailuo = _body("MiniMax-Hailuo-2.3-Fast", seconds=6)
    assert hailuo["duration"] == 6 and "generate_audio" not in hailuo and "aspect_ratio" not in hailuo


def _provider(handler):
    client = httpx.AsyncClient(base_url="https://api.evolink.ai", transport=httpx.MockTransport(handler))
    host = _Host()
    p = EvolinkVideoProvider(api_key="k", model="seedance-2.0-fast-image-to-video", image_host=host, client=client)
    return p, host


def test_submit_poll_and_fetch(tmp_path, monkeypatch):
    sent = {}

    def handler(request: httpx.Request):
        if request.method == "POST":
            sent.update(json.loads(request.content))
            return httpx.Response(200, json={"id": "task-1", "status": "pending", "usage": {"credits_reserved": 9.2}})
        return httpx.Response(200, json={"id": "task-1", "status": "completed",
                                         "results": ["https://cdn.example/v.mp4"], "usage": {"credits": 9.2}})

    p, host = _provider(handler)

    class _DL:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url): return httpx.Response(200, content=b"mp4")

    monkeypatch.setattr("app.videomake.providers.evolink_video.httpx.AsyncClient", _DL)
    frame = tmp_path / "image.png"
    frame.write_bytes(b"png")

    async def run():
        h = await p.submit(cut_index=2, motion_prompt="m", first_frame=frame, negative_prompt="n",
                           aspect_ratio="9:16", resolution="720p", duration_seconds=4, generate_audio=True)
        status = await p.poll(h)
        result = await p.fetch(h, tmp_path / "out.mp4")
        return h, status, result

    h, status, result = asyncio.run(run())
    assert sent["model"] == "seedance-2.0-fast-image-to-video" and sent["duration"] == 4
    assert host.keys[0].endswith("/cut02.png")
    assert h.operation_name == "task-1" and status.done and not status.failed
    assert (tmp_path / "out.mp4").read_bytes() == b"mp4"
    assert result.cost_usd > 0


def test_failed_task_is_reported():
    def handler(request):
        return httpx.Response(200, json={"id": "t", "status": "failed",
                                         "error": {"code": "content_filter", "message": "blocked"}})

    p, _ = _provider(handler)
    status = asyncio.run(p.poll(VideoHandle(cut_index=1, operation_name="t")))
    assert status.failed and "blocked" in status.error


def test_unknown_model_is_rejected():
    with pytest.raises(ProviderError):
        EvolinkVideoProvider(api_key="k", model="nope", image_host=_Host())


class _Rec:
    def __init__(self, name):
        self.name, self.calls = name, []

    def price_per_second(self, r):
        from decimal import Decimal
        return Decimal(0)

    async def submit(self, **kw):
        self.calls.append(kw)
        return VideoHandle(cut_index=kw["cut_index"], operation_name=f"{self.name}-{kw['cut_index']}")

    async def poll(self, h):
        return VideoStatus(done=True)

    async def fetch(self, h, dest):
        return VideoResult(path=f"{self.name}")


def test_speaking_cuts_go_to_the_dialogue_provider():
    cheap, veo = _Rec("cheap"), _Rec("veo")
    router = RoutingVideoProvider(default=cheap, speaking=veo)

    async def run():
        a = await router.submit(cut_index=1, speaking=False)
        b = await router.submit(cut_index=2, speaking=True)
        return a, b, await router.fetch(a, Path("x")), await router.fetch(b, Path("y"))

    a, b, fa, fb = asyncio.run(run())
    assert a.operation_name == "cheap-1" and b.operation_name == "veo-2"
    assert fa.path == "cheap" and fb.path == "veo"


def test_default_video_provider_is_still_veo():
    s = Settings(_env_file=None)
    assert s.video_provider == "veo" and s.dialogue_video_provider == "same"
