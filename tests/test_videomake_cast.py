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
    {"name": "지수", "appearance": "A woman with shoulder-length brown hair in a grey sweater. Slim.", "voice": "bright, a woman"},
    {"name": "엄마", "appearance": "A woman in her fifties with short permed hair. Warm smile.", "voice": "warm, older, a woman in her fifties"},
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


def test_on_screen_speaker_is_pointed_at_by_position_and_look(tmp_path):
    prompts = _motion(tmp_path, [([("지훈", "left"), ("지수", "right")], []), ([("지수", "right")], ["지수"])])
    motion = prompts[2]

    assert "FIRST, the person on the right side of the frame (A woman with shoulder-length brown hair in a grey sweater)" in motion
    assert "Only that person's lips move" in motion
    assert "지수 speaks" not in motion  # 이름만으로는 Veo가 누구인지 모른다
    # 혼자 보이는 화자는 화면 밖 상대 쪽(왼쪽)을 본다.
    assert "just outside the frame on the left side" in motion
    assert "Only this one person is in the frame." in motion


def test_off_screen_voice_cut_is_a_silent_listening_shot(tmp_path):
    """전화 속 목소리만 있는 컷은 Veo에게 말소리를 시키지 않는다 — 말소리를 만들면 화면 속
    듣는 사람의 입을 그 소리에 맞춰 움직였다. 목소리는 더빙이 넣는다."""
    prompts = _motion(tmp_path, [([("지훈", "center")], ["엄마"])])
    motion = prompts[1]

    assert "is listening to someone who is not in the frame" in motion
    assert "their lips never move" in motion
    assert "엄마의 말이에요." not in motion  # 대사를 Veo에게 주지 않는다
    assert "FIRST," not in motion


def test_two_people_on_screen_in_a_dialogue_cut_are_fed_back():
    payload = _payload([([("지훈", "left"), ("지수", "right")], ["지수"])])
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    assert "대사 컷에는 말하는 사람만 화면에" in [v.rule for v in lint_storyboard(sb)]


def test_listeners_may_share_the_frame_with_an_off_screen_voice():
    payload = _payload([([("지훈", "left"), ("지수", "right")], ["엄마"])])
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    assert "대사 컷에는 말하는 사람만 화면에" not in [v.rule for v in lint_storyboard(sb)]


def test_two_people_in_one_position_are_fed_back():
    payload = _payload([([("지훈", "left"), ("지수", "left")], [])])
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    assert "한 위치에 한 사람" in [v.rule for v in lint_storyboard(sb)]


def test_only_on_screen_supporting_get_a_sheet():
    payload = _payload([([("지훈", "center"), ("지수", "right")], []), ([("지훈", "center")], ["엄마"])])
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    assert [c.name for c in sb.on_screen_supporting] == ["지수"]


def test_dialogue_prompt_forbids_subtitles_and_camera_gaze(tmp_path):
    motion = _motion(tmp_path, [([("지훈", "left"), ("지수", "right")], []), ([("지훈", "left")], ["지훈"])])[2]

    assert "Absolutely no subtitles, captions, letters or any on-screen text" in motion
    assert "just outside the frame on the right side, never at the camera" in motion


def test_negative_prompts_block_burned_in_text():
    from app.videomake.prompts import get_prompts

    p = get_prompts()
    for negative in (p.video_negative_prompt, p.video_negative_prompt_dialogue):
        assert "korean text" in negative and "chinese characters" in negative


def test_alone_on_the_phone_has_no_one_beside_them(tmp_path):
    """전화 통화처럼 그 장소에 상대가 없으면 "화면 밖 상대"를 쓰지 않는다 — 엉뚱한 뒷모습이 그려졌다."""
    motion = _motion(tmp_path, [([("지훈", "center")], ["엄마"]), ([("지훈", "center")], ["지훈"])])[2]

    assert "just outside the frame" not in motion
    assert "Only this one person is in the frame." not in motion


def test_motion_keeps_held_objects_and_forbids_vanishing(tmp_path):
    motion = _motion(tmp_path, [([("지훈", "center")], [])])[1]

    assert "stays in the same hand" in motion
    assert "nothing in the scene appears, disappears" in motion


def test_mood_is_given_to_the_person_on_screen():
    """지수 혼자 나오는 컷의 감정 지시는 지수에게 — 화면에 없는 주인공(지훈)에게 붙이지 않는다."""
    from app.videomake.stages.cut_images import mood_subject

    payload = _payload([
        ([("지훈", "left"), ("지수", "right")], []),
        ([("지수", "right")], ["지수"]),
        ([], []),
    ])
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    assert mood_subject(sb, sb.cut(1)) == "지훈"  # 주인공이 보이면 주인공
    assert mood_subject(sb, sb.cut(2)) == "지수"  # 지수만 보이면 지수
    assert mood_subject(sb, sb.cut(3)) == "지훈"  # 아무도 없으면 장면 분위기(주인공)


def test_voice_off_screen_only_when_no_speaker_is_visible():
    from app.videomake.stages.cut_images import voice_off_screen

    payload = _payload([
        ([("지훈", "center")], ["엄마"]),
        ([("지훈", "center")], ["지훈"]),
        ([("지훈", "center")], []),
    ])
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    assert voice_off_screen(sb, sb.cut(1))
    assert not voice_off_screen(sb, sb.cut(2))
    assert not voice_off_screen(sb, sb.cut(3))
