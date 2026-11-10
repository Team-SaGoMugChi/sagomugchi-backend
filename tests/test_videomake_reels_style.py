"""릴스식 연출(2026-11): 한 대사 한 샷의 빠른 주고받기, 물건 클로즈업(insert), 시간 글자, 처음부터 끝까지 깔리는 배경음악.
외부 API는 쓰지 않는다(비용 0)."""

import shutil
import wave

import numpy as np
import pytest
from pydantic import ValidationError

from app.videomake.config import Settings
from app.videomake.guardrails import MAX_DIALOGUE_CUTS, lint_dialogue_count
from app.videomake.models import Cut, EditPlan, MusicCue
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.stages.compose import _duck_music, _prepare_video, _time_card, edit_lengths
from app.videomake.stages.edit_plan import DEFAULT_MUSIC_PROMPT, cover_all
from app.videomake.stages.storyboard import _StoryboardDraft

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")


def _sb(kinds):
    """kinds: 컷마다 "n"(나레이션) / "d"(대사)."""
    payload = fake.demo_storyboard_payload(len(kinds))
    for cut, kind in zip(payload["cuts"], kinds):
        cut["duration_seconds"] = 4
        if kind == "d":
            cut["narration"], cut["dialogue"] = "", [{"speaker": "지훈", "text": "괜찮아요."}]
    return _StoryboardDraft.model_validate(payload).to_storyboard()


def _tone_wav(path, *, seconds, speech=(0.5, 2.0), rate=24_000):
    """speech 구간에만 소리가 있는 파일(말소리 대신)."""
    t = np.arange(int(rate * seconds)) / rate
    on = (t >= speech[0]) & (t < speech[1])
    samples = (np.sin(2 * np.pi * 220 * t) * 12_000 * on).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(samples.tobytes())
    return path


@needs_ffmpeg
def test_dialogue_exchange_cuts_right_after_the_line(tmp_path):
    sb = _sb(["d", "d", "n"])
    voice = {i: _tone_wav(tmp_path / f"d{i}.wav", seconds=4) for i in (1, 2)}
    settings = Settings(_env_file=None, edit_tail_seconds=1.1, edit_exchange_tail_seconds=0.5)
    lengths = edit_lengths(sb, settings=settings, narrations={}, voice_of=voice, hold=set(), delay=0.3)
    # 대사 끝 약 2.0초. 다음 컷도 대사면 0.5초만 두고 넘기고, 나레이션으로 넘어갈 때는 평소 여유(1.1초).
    assert lengths[0] == pytest.approx(2.5, abs=0.1)
    assert lengths[1] == pytest.approx(3.1, abs=0.1)


def test_insert_cut_shows_things_only():
    Cut(index=1, image_prompt="a pruning shear on the bench", motion_prompt="m", camera_distance="insert")
    with pytest.raises(ValidationError, match="insert 컷"):
        Cut(index=1, image_prompt="i", motion_prompt="m", camera_distance="insert",
            cast=[{"name": "지훈", "position": "center"}])


def test_time_card_is_short():
    Cut(index=1, image_prompt="i", motion_prompt="m", time_card="다음 날")
    with pytest.raises(ValidationError, match="time_card"):
        Cut(index=1, image_prompt="i", motion_prompt="m", time_card="그로부터 일주일이 지난 뒤")


def test_insert_cut_draws_no_one():
    from app.videomake.stages.cut_images import cut_image_request

    sb = _sb(["n", "n"])
    cut = sb.cuts[1]
    cut.camera_distance, cut.cast = "insert", []
    assert sb.visible_cast(cut) == []
    text, refs = cut_image_request(sb, cut, sheets={sb.protagonist.name: "sheet.png"}, location_sheets={},
                                   prompts=get_prompts(), aspect_ratio="9:16")
    assert "NO people at all" in text and "NOT a view of the room" in text and "MEDIUM SHOT" not in text
    assert "sheet.png" not in [str(r) for r in refs]  # 인물 시트를 주지 않는다


def test_too_many_dialogue_cuts_is_fed_back():
    assert lint_dialogue_count(_sb(["n"] + ["d"] * MAX_DIALOGUE_CUTS)) == []
    assert lint_dialogue_count(_sb(["n"] + ["d"] * (MAX_DIALOGUE_CUTS + 1)))


def test_planner_prompt_leads_with_dialogue_and_knows_the_new_fields():
    from app.videomake.stages.storyboard import system_prompt

    text = system_prompt(get_prompts(), Settings(_env_file=None))
    assert "대화는 대사로, 이야기 연결은 나레이션으로" in text
    assert f"많아야 {MAX_DIALOGUE_CUTS}개" in text
    assert "일기에 없는 말은 만들지 않는다" in text
    assert "time_card" in text and "insert" in text


# --- 배경음악 ---------------------------------------------------------------


def test_music_covers_the_whole_video_without_gaps():
    sb = _sb(["n"] * 6)
    one = cover_all(EditPlan(music=[MusicCue(from_cut=3, to_cut=4, prompt="a")]), sb)
    assert [(m.from_cut, m.to_cut) for m in one.music] == [(1, 6)]
    two = cover_all(EditPlan(music=[MusicCue(from_cut=2, to_cut=3, prompt="a"),
                                    MusicCue(from_cut=5, to_cut=5, prompt="b")]), sb)
    assert [(m.from_cut, m.to_cut, m.prompt) for m in two.music] == [(1, 3, "a"), (4, 6, "b")]
    none = cover_all(EditPlan(), sb)
    assert [(m.from_cut, m.to_cut, m.prompt) for m in none.music] == [(1, 6, DEFAULT_MUSIC_PROMPT)]


def _rms_db(samples):
    return 20 * np.log10(np.sqrt(np.mean((samples.astype(np.float64) / 32768) ** 2)) + 1e-9)


def test_music_is_lowered_only_while_someone_speaks(tmp_path):
    rate = 48_000
    t = np.arange(rate * 6) / rate
    tone = (np.sin(2 * np.pi * 330 * t) * 8000).astype(np.int16)
    path = tmp_path / "m.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(np.repeat(tone, 2).tobytes())
    _duck_music(path, [(2.0, 4.0)], duck_db=-12.0)
    with wave.open(str(path), "rb") as wf:
        out = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)[::2]
    before, during, after = out[: rate], out[int(2.5 * rate): int(3.5 * rate)], out[5 * rate:]
    assert _rms_db(during) == pytest.approx(_rms_db(before) - 12, abs=0.5)
    assert _rms_db(after) == pytest.approx(_rms_db(before), abs=0.5)


# --- 시간 글자 ---------------------------------------------------------------


@needs_ffmpeg
def test_time_card_is_drawn_over_the_start_of_the_cut(tmp_path):
    import subprocess

    card = _time_card("다음 날", tmp_path / "card.png", size=(360, 640))
    if card is None:
        pytest.skip("한글 글꼴 없음")
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=360x640:d=3", str(src)], check=True)
    out = tmp_path / "out.mp4"
    _prepare_video(src, out, seconds=3.0, size=(360, 640), card=card)

    def frame(at):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(out), "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return np.frombuffer(raw, dtype=np.uint8).reshape(640, 360, 3)

    yellow = lambda f: int(((f[..., 0] > 200) & (f[..., 1] > 180) & (f[..., 2] < 120)).sum())  # noqa: E731
    assert yellow(frame(0.5)) > 200  # 글자가 보인다
    assert yellow(frame(2.5)) == 0  # 잠깐 뒤에는 사라진다
