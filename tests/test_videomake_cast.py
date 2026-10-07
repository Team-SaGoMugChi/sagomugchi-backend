"""조연 시트·출연자 위치 — 대사 컷에서 누가 말하는지 위치·외모로 가리킨다. 비용 0."""

import asyncio
import shutil

import pytest

from app.videomake.config import Settings
from app.videomake.guardrails import lint_storyboard
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.registry import build_fake_providers
from app.videomake.stages.storyboard import _StoryboardDraft

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")

SUPPORTING = [
    {"name": "지수", "appearance": "A woman with shoulder-length brown hair in a grey sweater. Slim.", "voice": "bright"},
    {"name": "엄마", "appearance": "A woman in her fifties with short permed hair. Warm smile.", "voice": "warm, older"},
]


class _RecordingVideo(fake.FakeVideo):
    def __init__(self):
        super().__init__()
        self.prompts = {}

    async def submit(self, *, cut_index, motion_prompt, **kwargs):
        self.prompts[cut_index] = motion_prompt
        return await super().submit(cut_index=cut_index, motion_prompt=motion_prompt, **kwargs)


def _payload(cuts):
    """cuts: (cast, dialogue 화자 목록) 목록."""
    payload = fake.demo_storyboard_payload(len(cuts))
    payload["supporting"] = SUPPORTING
    for cut, (cast, speakers) in zip(payload["cuts"], cuts):
        cut["cast"] = [{"name": n, "position": p} for n, p in cast]
        if speakers:
            cut.update(narration="", duration_seconds=6,
                       dialogue=[{"speaker": s, "text": f"{s}의 말이에요."} for s in speakers])
    return payload


def _motion(tmp_path, cuts):
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0,
                        min_cuts=1, min_total_seconds=4)
    base = build_fake_providers(settings)
    llm = fake.FakeLLM(len(cuts))
    llm.payload = _payload(cuts)
    video = _RecordingVideo()
    providers = base.__class__(**{**base.__dict__, "llm": llm, "video": video})
    pipe = Pipeline(providers=providers, job=JobStore(settings.jobs_dir, "cast"), settings=settings)

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        await pipe.render(sb)

    asyncio.run(run())
    return video.prompts


def test_on_screen_speakers_are_pointed_at_by_position_and_look(tmp_path):
    prompts = _motion(tmp_path, [([("지훈", "left"), ("지수", "right")], ["지수", "지훈"])])
    motion = prompts[1]

    assert "FIRST, the person on the right side of the frame (A woman with shoulder-length brown hair in a grey sweater)" in motion
    assert "THEN, the person on the left side of the frame" in motion
    assert "Only that person's lips move" in motion
    assert "지수 speaks" not in motion  # 이름만으로는 Veo가 누구인지 모른다


def test_speaker_not_in_the_frame_is_an_off_screen_voice(tmp_path):
    prompts = _motion(tmp_path, [([("지훈", "center")], ["엄마", "지훈"])])
    motion = prompts[1]

    assert "FIRST, an off-screen voice that is not anyone in the frame speaks" in motion
    assert "Nobody in the frame moves their lips for this line" in motion
    assert "THEN, the person on the center side of the frame" in motion


def test_two_people_in_one_position_are_fed_back():
    payload = _payload([([("지훈", "left"), ("지수", "left")], [])])
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    assert "한 위치에 한 사람" in [v.rule for v in lint_storyboard(sb)]


def test_only_on_screen_supporting_get_a_sheet():
    payload = _payload([([("지훈", "center"), ("지수", "right")], []), ([("지훈", "center")], ["엄마", "지훈"])])
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    assert [c.name for c in sb.on_screen_supporting] == ["지수"]
