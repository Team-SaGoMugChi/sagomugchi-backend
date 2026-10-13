"""대사 더빙 — Veo의 입 모양 시각에 인물별 TTS 목소리를 맞춰 넣는다. 비용 0."""

import asyncio
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
