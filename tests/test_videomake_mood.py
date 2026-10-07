"""컷 감정(mood)이 그림·영상 지시에 드러나는지. 모든 provider가 가짜라 비용 0."""

import asyncio
import shutil

import pytest
from pydantic import ValidationError

from app.videomake.config import Settings
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.registry import build_fake_providers
from app.videomake.stages.storyboard import _StoryboardDraft, system_prompt

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")

MOODS = ["평온", "기쁨", "슬픔"]


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)


class _RecordingImage(fake.FakeImage):
    def __init__(self):
        self.prompts = []

    async def generate(self, *, prompt, **kwargs):
        self.prompts.append(prompt)
        return await super().generate(prompt=prompt, **kwargs)


class _RecordingVideo(fake.FakeVideo):
    def __init__(self):
        super().__init__()
        self.prompts = []

    async def submit(self, *, motion_prompt, **kwargs):
        self.prompts.append(motion_prompt)
        return await super().submit(motion_prompt=motion_prompt, **kwargs)


def _payload():
    payload = fake.demo_storyboard_payload(3)
    for cut, mood in zip(payload["cuts"], MOODS):
        cut["mood"] = mood
    return payload


def _run(tmp_path):
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0)
    base = build_fake_providers(settings)
    llm = fake.FakeLLM(3)
    llm.payload = _payload()
    image, video = _RecordingImage(), _RecordingVideo()
    providers = base.__class__(**{**base.__dict__, "llm": llm, "image": image, "video": video})
    pipe = Pipeline(providers=providers, job=JobStore(settings.jobs_dir, "mood"), settings=settings)

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        await pipe.finish(sb)
        return sb

    return asyncio.run(run()), image.prompts, video.prompts


def test_each_cut_mood_reaches_image_and_video_prompts(tmp_path):
    sb, image_prompts, video_prompts = _run(tmp_path)
    cut_prompts = image_prompts[1:]  # 첫 번째는 캐릭터 시트

    assert [c.mood for c in sb.cuts] == MOODS
    assert "calm and at ease" in cut_prompts[0]
    assert "warm, bright natural light" in cut_prompts[1]
    assert "a natural smile" in cut_prompts[1]
    assert "quietly sad" in cut_prompts[2]
    assert "calm and at ease" in video_prompts[0]
    assert "warm, light and happy" in video_prompts[1]
    assert "quietly sad" in video_prompts[2]


def test_fixed_gloom_is_gone_from_every_prompt(tmp_path):
    _, image_prompts, video_prompts = _run(tmp_path)

    for prompt in image_prompts + video_prompts:
        assert "desaturated" not in prompt
        assert "restrained" not in prompt
        assert "mouth is closed" not in prompt
    # 과장 금지는 남는다.
    assert all("never exaggerated" in p for p in image_prompts[1:])
    # 그림 모델에 한글이 들어가면 글자로 찍힐 수 있다 — 감정 이름은 넣지 않는다.
    assert all(m not in p for m in MOODS for p in image_prompts[1:])


def test_storyboard_must_choose_a_known_mood():
    payload = _payload()
    payload["cuts"][0]["mood"] = "설렘"
    with pytest.raises(ValidationError):
        _StoryboardDraft.model_validate(payload)

    del payload["cuts"][0]["mood"]
    with pytest.raises(ValidationError):
        _StoryboardDraft.model_validate(payload)


def test_planner_is_told_to_show_joy_where_the_diary_was_happy():
    system = system_prompt(get_prompts(), Settings(_env_file=None))

    assert "### mood" in system
    assert "반드시 기쁨" in system
    assert "낮은 채도" not in system
