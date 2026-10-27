"""컷 영상 검사 — 끝에 튀는 조각 덮기·샷 수·같은 사람 둘/없던 사람. 외부 API 없음, 비용 0."""

import asyncio
import json
import subprocess

from app.videomake.job import JobStore
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.base import CastCheck, SeenFrame
from app.videomake.stages.storyboard import _StoryboardDraft
from app.videomake.stages.video_check import (
    check_cut_video,
    cover_tail_flash,
    scene_cuts,
    shot_issue,
)


def _sb():
    return _StoryboardDraft.model_validate(fake.demo_storyboard_payload(2)).to_storyboard()


def _clip(path, parts):
    """색 화면을 이어 붙인 짧은 영상(소리 포함). parts: [(색, 초)]."""
    inputs, n = [], len(parts)
    for color, sec in parts:
        inputs += ["-f", "lavfi", "-i", f"color=c={color}:s=180x320:r=24:d={sec}"]
    total = sum(sec for _, sec in parts)
    inputs += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={total}"]
    concat = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", concat,
         "-map", "[v]", "-map", f"{n}:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(path)],
        check=True,
    )
    return path


def test_short_flash_at_the_end_is_covered_with_a_freeze(tmp_path):
    clip = _clip(tmp_path / "v.mp4", [("red", 3), ("blue", 2.8), ("red", 0.2)])
    cuts, duration = scene_cuts(clip)
    assert [round(t, 1) for t in cuts] == [3.0, 5.8]
    assert cover_tail_flash(clip, cuts, duration) is not None
    after, new_duration = scene_cuts(clip)
    assert [round(t, 1) for t in after] == [3.0]  # 튀는 조각이 사라졌다
    assert abs(new_duration - duration) < 0.1  # 길이는 그대로(나레이션 시간표 유지)


def test_flash_starting_between_rounded_times_is_fully_covered(tmp_path):
    # Veo 실측: 조각이 7.791667초(24fps 프레임 경계)에서 시작했다. 반올림하면 첫 프레임이 남는다.
    clip = _clip(tmp_path / "v.mp4", [("red", 3), ("blue", 187 / 24 - 3), ("red", 5 / 24)])
    cuts, duration = scene_cuts(clip)
    assert cover_tail_flash(clip, cuts, duration) is not None
    assert len(scene_cuts(clip)[0]) == 1


def test_a_real_last_shot_is_not_touched(tmp_path):
    clip = _clip(tmp_path / "v.mp4", [("red", 3), ("blue", 3)])
    cuts, duration = scene_cuts(clip)
    assert cover_tail_flash(clip, cuts, duration) is None


def test_shot_count_must_match_the_plan():
    cut = _sb().cuts[0]
    assert shot_issue(cut, []) is None  # 한 샷 컷
    assert "1번" in shot_issue(cut, [4.0])


class _CloneLook:
    def __init__(self):
        self.casts = []

    async def look(self, *, image, place=None, cast=None):
        self.casts.append(cast)
        return SeenFrame(people=[], looks_at_camera=False, duplicate_person=len(self.casts) == 2,
                         unknown_person=False)


def test_clone_in_a_shot_is_reported_for_rerender(tmp_path):
    sb = _sb()
    cut = sb.cuts[0]
    job = JobStore(tmp_path, "j")
    job.cut_dir(cut.index).mkdir(parents=True, exist_ok=True)
    clip = _clip(tmp_path / "v.mp4", [("red", 3), ("blue", 3)])
    look = _CloneLook()
    result = asyncio.run(check_cut_video(sb, cut, clip, look=look, job=job))
    assert len(look.casts) == 2 and isinstance(look.casts[0], CastCheck)
    assert any("같은 사람이 두 번" in i for i in result.issues)
    saved = json.loads((job.cut_dir(cut.index) / "video_check.json").read_text(encoding="utf-8"))
    assert saved["issues"] == result.issues


def test_video_prompt_names_who_is_in_the_scene_and_bans_clones():
    p = get_prompts()
    text = p.render("motion.j2", motion_prompt="She takes the bag.", shots=[], duration=8,
                    people=["Jieun, a woman in her thirties", "the elderly owner"],
                    dialogue=[], solo_side="", ambient=False, listening=False, mood_line="")
    assert "Exactly 2 different people are in this clip" in text
    assert "never two copies of the same person" in text
    assert "nothing is handed over and then taken back" in text
    assert "no English words" in text
    assert "duplicate person" in p.video_negative_prompt and "tear streaks" in p.video_negative_prompt


def test_sad_cut_holds_back_tears_without_drops():
    p = get_prompts()
    sad = p.render("mood.j2", mood="슬픔", name="지은", part="motion")
    assert "holding back tears" in sad and "no tear drops fall" in sad
    assert "tear" not in p.render("mood.j2", mood="기쁨", name="지은", part="motion")


def test_later_shots_continue_the_same_moment_and_position():
    from app.videomake.models import Shot

    shots = [Shot(seconds=4, framing="medium", view="a"), Shot(seconds=4, framing="insert", view="b")]
    text = get_prompts().render("motion.j2", motion_prompt="x", shots=shots, duration=8, people=[],
                                dialogue=[], solo_side="", ambient=False, listening=False, mood_line="")
    assert "starts no new action" in text
    assert "never move them onto a counter" in text


def test_continuity_frames_cover_both_sides_of_every_cut():
    from app.videomake.stages.video_check import continuity_times

    times = continuity_times([2.4, 6.5], 8.0)
    assert [k for _, k in times] == [1, 1, 1, 2, 2, 2, 3, 3, 3]
    assert any(2.0 < t < 2.4 for t, _ in times) and any(2.4 < t < 2.8 for t, _ in times)


class _ContinuityLook(_CloneLook):
    def __init__(self):
        super().__init__()
        self.frames = None

    async def continuity(self, *, frames, scene):
        self.frames = frames
        return ["6.3s 할머니가 지폐를 다시 건넨다"]


def test_continuity_errors_are_reported_only_for_multi_shot_cuts(tmp_path):
    sb = _sb()
    cut = sb.cuts[0]
    job = JobStore(tmp_path, "j")
    job.cut_dir(cut.index).mkdir(parents=True, exist_ok=True)
    look = _ContinuityLook()
    one_shot = _clip(tmp_path / "a.mp4", [("red", 4)])
    asyncio.run(check_cut_video(sb, cut, one_shot, look=look, job=job))
    assert look.frames is None  # 샷이 하나면 연결 확인을 하지 않는다
    two_shots = _clip(tmp_path / "b.mp4", [("red", 3), ("blue", 3)])
    result = asyncio.run(check_cut_video(sb, cut, two_shots, look=look, job=job))
    assert look.frames and look.frames[0].shot == 1 and look.frames[-1].shot == 2
    assert "샷 연결: 6.3s 할머니가 지폐를 다시 건넨다" in result.issues
