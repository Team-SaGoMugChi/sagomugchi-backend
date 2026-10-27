"""대사 더빙 — Veo의 입 모양 시각에 인물별 TTS 목소리를 맞춰 넣는다. 비용 0."""

import asyncio
import json
import shutil

import numpy as np
import pytest

from app.videomake.config import Settings
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput, Storyboard
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.registry import build_fake_providers
from app.videomake.stages.dialogue_voice import (
    MAX_GAIN_DB,
    TEMPO_HARD_MAX,
    assign_voices,
    level_gain_db,
    plan_slots,
    speech_segments,
    spoken_text,
    voice_gender,
)

RATE = 16_000


def _storyboard(supporting):
    payload = fake.demo_storyboard_payload(3)
    payload["protagonist"]["voice"] = "clear, mid-pitched, a Korean man in his late twenties"
    payload["supporting"] = supporting
    return Storyboard.model_validate(payload)


def _signal(seconds, bursts, noise_db=-60.0):
    """룸톤 위에 말소리 대신 사인파 구간을 얹는다. bursts: (시작, 끝) 초."""
    t = np.arange(int(seconds * RATE)) / RATE
    rng = np.random.default_rng(0)
    x = rng.normal(0, 10 ** (noise_db / 20), t.size)
    for a, b in bursts:
        on = (t >= a) & (t < b)
        x[on] += 0.3 * np.sin(2 * np.pi * 220 * t[on])
    return (np.clip(x, -1, 1) * 32767).astype(np.int16)


def test_voice_gender_reads_woman_before_man():
    assert voice_gender("higher-pitched, a Korean woman in her twenties") == "f"
    assert voice_gender("deep, a man in his forties") == "m"
    assert voice_gender("warm and calm") is None


def test_each_person_gets_a_distinct_voice_that_is_not_the_narrator():
    sb = _storyboard([
        {"name": "지수", "appearance": "A woman with a bob.", "voice": "bright, a woman in her twenties"},
        {"name": "수아", "appearance": "A woman with long hair.", "voice": "soft, a woman in her twenties"},
        {"name": "민호", "appearance": "A man with glasses.", "voice": "low, a man in his thirties"},
    ])
    voices = assign_voices(sb, narrator_voice="Kore")

    assert len(set(voices.values())) == 4
    assert "Kore" not in voices.values()
    assert voices["지훈"] in ("Puck", "Charon", "Orus", "Fenrir")
    assert voices["지수"] in ("Aoede", "Despina", "Zephyr")


def test_speech_segments_finds_lines_and_drops_short_blips():
    samples = _signal(6.0, [(0.0, 0.15), (1.0, 2.5), (2.65, 2.9), (3.6, 5.0)])
    segments = speech_segments(samples)

    # 0.15초 잡음은 버리고, 0.15초 쉼은 한 줄로 이어 붙인다.
    assert len(segments) == 2
    assert segments[0][0] == pytest.approx(1.0, abs=0.05)
    assert segments[0][1] == pytest.approx(2.9, abs=0.05)
    assert segments[1][0] == pytest.approx(3.6, abs=0.05)


def test_silent_audio_has_no_segments():
    assert speech_segments(_signal(6.0, [])) == []


def test_extra_segment_from_veo_is_dropped_and_lines_follow_mouth_timing():
    # Veo가 대본 앞에 짧은 말을 덧붙인 경우 — 긴 두 구간이 대사 두 줄이다.
    slots = plan_slots([(0.0, 0.46), (1.68, 3.18), (3.7, 5.06)], [1.6, 1.4], 6)

    assert [s.start for s in slots] == [1.68, 3.7]
    assert all(0.85 <= s.tempo <= 1.3 for s in slots)


def test_lines_without_detected_speech_follow_each_other():
    slots = plan_slots([], [1.5, 1.5], 6)

    assert slots[0].start == pytest.approx(0.8)
    assert slots[1].start >= slots[0].start + slots[0].seconds


def test_lines_longer_than_the_clip_are_packed_inside_it():
    slots = plan_slots([(1.0, 2.0), (2.5, 3.5)], [3.0, 3.0], 6)
    end = slots[-1].start + slots[-1].seconds

    assert end <= 6.0
    assert all(s.tempo <= TEMPO_HARD_MAX for s in slots)
    assert slots[1].start >= slots[0].start + slots[0].seconds


def test_line_without_ending_punctuation_gets_a_period():
    assert spoken_text("너 요즘 맨날 늦는다") == "너 요즘 맨날 늦는다."
    assert spoken_text("왜 늦었어?") == "왜 늦었어?"


def test_quiet_line_is_raised_toward_narration_level():
    quiet = _signal(1.5, [(0.1, 1.4)], noise_db=-80)
    quiet = (quiet * 0.05).astype(np.int16)  # 약 -36dB

    assert level_gain_db(quiet, RATE) == pytest.approx(MAX_GAIN_DB)
    assert level_gain_db(_signal(1.5, [(0.1, 1.4)]), RATE) < 3


def _pipeline(tmp_path, monkeypatch, **overrides):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0,
                        min_cuts=1, min_total_seconds=4, **overrides)
    base = build_fake_providers(settings)
    llm = fake.FakeLLM(2)
    payload = fake.demo_storyboard_payload(2)
    payload["supporting"] = [
        {"name": "지수", "appearance": "A woman with a bob.", "voice": "bright, a woman"},
    ]
    payload["cuts"][1].update(
        narration="", duration_seconds=4,
        cast=[{"name": "지수", "position": "right"}],
        dialogue=[{"speaker": "지수", "text": "왜 늦었어"}],
    )
    llm.payload = payload
    providers = base.__class__(**{**base.__dict__, "llm": llm, "tts": fake.FakeTTS(seconds=1.0)})
    return Pipeline(providers=providers, job=JobStore(settings.jobs_dir, "dub"), settings=settings)


def _finish(pipe):
    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        return await pipe.finish(sb)

    return asyncio.run(run())


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_dialogue_cut_is_dubbed_and_composed(tmp_path, monkeypatch):
    pipe = _pipeline(tmp_path, monkeypatch)
    final = _finish(pipe)

    assert final.exists()
    assert pipe.job.cut_dialogue(2).exists()
    assert not pipe.job.cut_dialogue(1).exists()  # 나레이션 컷은 더빙하지 않는다
    assert (pipe.job.cut_dir(2) / "line_1.wav").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_veo_voice_setting_keeps_veo_audio(tmp_path, monkeypatch):
    pipe = _pipeline(tmp_path, monkeypatch, dialogue_voice="veo")
    final = _finish(pipe)

    assert final.exists()
    assert not pipe.job.cut_dialogue(2).exists()


def test_character_without_clear_gender_is_fed_back():
    from app.videomake.guardrails import lint_storyboard

    payload = fake.demo_storyboard_payload(3)
    payload["protagonist"]["appearance"] = "A Korean young adult in their mid twenties with short black hair."
    payload["protagonist"]["voice"] = "clear and bright, a young adult"
    sb = Storyboard.model_validate(payload)

    assert "인물 성별을 분명히" in [v.rule for v in lint_storyboard(sb)]
    assert "인물 성별을 분명히" not in [v.rule for v in lint_storyboard(_storyboard([]))]


def test_take_closest_to_mouth_timing_is_chosen():
    from app.videomake.stages.dialogue_voice import pick_take, target_lengths

    assert target_lengths([(0.0, 0.4), (1.24, 3.38)], 1) == [2.14]
    assert target_lengths([], 1) == [None]
    assert pick_take([3.35, 2.3, 2.9], 2.14) == 1
    assert pick_take([3.35, 2.3, 2.9], None) == 1  # 입 시간을 모르면 가장 짧은 읽기


def test_off_screen_line_keeps_its_natural_speed():
    """맞출 입이 없으면(구간 없음) 원래 속도로 컷 시작 조금 뒤에 놓는다."""
    slot = plan_slots([], [3.1], 6)[0]

    assert slot.tempo == pytest.approx(1.0)
    assert slot.start == pytest.approx(0.8)


def test_veo_voice_check_rules():
    from app.videomake.providers.base import HeardSpeech
    from app.videomake.stages.dialogue_voice import veo_voice_ok

    line = "그거 제 기획서에 있던 내용 아니에요?"
    assert veo_voice_ok(line, HeardSpeech(text="그거 제 기획서에 있던 내용 아니에요", voice="f"), "f")[0]
    assert veo_voice_ok("마지막이니까 단팥빵 두 개 그냥 가져가.", HeardSpeech(text="마지막이니까 단팥빵 두개 그냥 가져가", voice=""), "f")[0]
    # 대본 뒤에 웅얼거림을 덧붙임 (실제 대표 영상에서 관측)
    ok, why = veo_voice_ok(line, HeardSpeech(text=line + " 며칠을 너무 차고 있었는데", voice="f"), "f")
    assert not ok and "덧붙" in why
    assert not veo_voice_ok(line, HeardSpeech(text=line, voice="m"), "f")[0]  # 여자 인물인데 남자 목소리
    # 끝에 짧은 말을 덧붙임 (실제 관측: "…굴지 마. 한기유.")
    long_line = "팀 아이디어는 다 같이 한 거고, 너무 예민하게 굴지 마."
    assert not veo_voice_ok(long_line, HeardSpeech(text="이 팀 아이디어는 다 같이 한 거고. 너무 예민하게 굴지 마. 한기유.", voice="m"), "m")[0]
    assert not veo_voice_ok(line, HeardSpeech(text="", voice=""), "f")[0]
    assert not veo_voice_ok(line, HeardSpeech(text="오늘 회의 정말 좋았어요 다들", voice="f"), "f")[0]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_auto_keeps_veo_voice_when_it_says_the_script(tmp_path, monkeypatch):
    from app.videomake.providers.base import HeardSpeech

    pipe = _pipeline(tmp_path, monkeypatch)
    listen = fake.FakeListen(HeardSpeech(text="왜 늦었어", voice="f"))
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "listen": listen})
    final = _finish(pipe)

    assert final.exists()
    assert len(listen.calls) == 1  # 대사 컷만 듣는다
    assert not pipe.job.cut_dialogue(2).exists()
    assert not (pipe.job.cut_dir(2) / "line_1.wav").exists()  # TTS를 부르지 않았다
    assert '"keep_veo_voice": true' in (pipe.job.cut_dir(2) / "voice_check.json").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_auto_dubs_when_veo_adds_words(tmp_path, monkeypatch):
    from app.videomake.providers.base import HeardSpeech

    pipe = _pipeline(tmp_path, monkeypatch)
    listen = fake.FakeListen(HeardSpeech(text="왜 늦었어 진짜 너무하다 정말", voice="f"))
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "listen": listen})
    _finish(pipe)

    assert pipe.job.cut_dialogue(2).exists()
    assert '"keep_veo_voice": false' in (pipe.job.cut_dir(2) / "voice_check.json").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_auto_dubs_when_listening_fails(tmp_path, monkeypatch):
    class _Broken:
        async def listen(self, *, audio):
            raise RuntimeError("network")

    pipe = _pipeline(tmp_path, monkeypatch)
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "listen": _Broken()})
    _finish(pipe)
    assert pipe.job.cut_dialogue(2).exists()


def test_default_dialogue_voice_is_auto():
    assert Settings(_env_file=None).dialogue_voice == "auto"


def test_listen_reply_as_list_is_read():
    from app.videomake.providers.gemini_listen import parse_heard

    assert parse_heard('[{"text": "안녕", "voice": "f"}]')["text"] == "안녕"
    assert parse_heard('{"text": "안녕", "voice": "m"}')["voice"] == "m"
    assert parse_heard("[]") == {}


def _cut_check_sb():
    from app.videomake.models import Storyboard

    payload = fake.demo_storyboard_payload(2)
    payload["supporting"] = [{"name": "본부장", "appearance": "A man in his fifties with gray hair.", "voice": "low, a man"}]
    payload["cuts"][1].update(narration="", camera_distance="medium", cast=[{"name": "본부장", "position": "right"}],
                              dialogue=[{"speaker": "본부장", "text": "좋은 아이디어네요."}], duration_seconds=4)
    return Storyboard.model_validate(payload)


def test_image_check_finds_small_wrong_gender_and_camera_gaze():
    from app.videomake.providers.base import SeenFrame, SeenPerson
    from app.videomake.stages.cut_images import image_problems

    sb = _cut_check_sb()
    cut = sb.cuts[1]
    ok = SeenFrame(people=[SeenPerson(gender="m", height_ratio=0.6)], looks_at_camera=False)
    assert image_problems(sb, cut, ok) == []
    # 실제 관측: 허리 위 샷인데 아주 작게, 50대 남자를 여자로
    bad = SeenFrame(people=[SeenPerson(gender="f", height_ratio=0.15)], looks_at_camera=True)
    problems = " ".join(image_problems(sb, cut, bad))
    assert "MEDIUM" in problems and "man" in problems and "camera" in problems
    # 실제 관측: 키는 크게 어림(0.61)했지만 다리까지 보이는 전신 — 허리 위 샷이 아니다
    full_body = SeenFrame(people=[SeenPerson(gender="m", height_ratio=0.61, legs_visible=True)], looks_at_camera=False)
    assert "MEDIUM" in " ".join(image_problems(sb, cut, full_body))
    empty = SeenFrame(people=[SeenPerson(gender="m", height_ratio=0.03)], looks_at_camera=False)  # 배경 행인뿐
    assert "Only 0" in " ".join(image_problems(sb, cut, empty))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
def test_wrong_cut_image_is_redrawn_with_the_problem(tmp_path, monkeypatch):
    from app.videomake.providers.base import SeenFrame, SeenPerson

    class _Look:
        def __init__(self):
            self.n = 0

        async def look(self, *, image, place=None):
            self.n += 1  # 첫 그림만 카메라를 본다
            return SeenFrame(people=[SeenPerson(gender="", height_ratio=0.6)] * 2, looks_at_camera=self.n == 1)

    class _Image(fake.FakeImage):
        def __init__(self):
            super().__init__()
            self.prompts = []

        async def generate(self, *, prompt, dest, **kw):
            self.prompts.append(prompt)
            return await super().generate(prompt=prompt, dest=dest, **kw)

    pipe = _pipeline(tmp_path, monkeypatch)
    img = _Image()
    pipe.p = pipe.p.__class__(**{**pipe.p.__dict__, "look": _Look(), "image": img})

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        return sb

    asyncio.run(run())
    redraws = [p for p in img.prompts if "THE PREVIOUS ATTEMPT WAS WRONG" in p]
    assert len(redraws) == 1  # 첫 검사에서 틀린 그림 하나만 다시 그린다
    checks = [json.loads(p.read_text(encoding="utf-8")) for p in pipe.job.dir.glob("cuts/*/image_check.json")]
    assert sorted(len(c) for c in checks) == [1, 2]  # 다시 그린 컷은 검사 기록이 두 번
    assert any(c[0]["problems"] for c in checks)
