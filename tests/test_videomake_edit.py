"""정적 자르기·편집 계획·배경음악·나레이션 목소리(Fish). 외부 API는 가짜라 비용 0."""

import asyncio
import json
import shutil
import subprocess
import wave
from decimal import Decimal

import pytest

from app.videomake.config import Settings
from app.videomake.cost import fish_price
from app.videomake.guardrails import lint_narration
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput, EditPlan, MusicCue, Shot
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.base import LLMResult
from app.videomake.providers.fish_tts import FallbackTTS
from app.videomake.providers.registry import build_fake_providers, build_narration_tts
from app.videomake.stages.compose import _music_track, edit_lengths
from app.videomake.stages.edit_plan import load_plan, make_music, plan_edit
from app.videomake.stages.storyboard import _StoryboardDraft

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")
LINE = [{"speaker": "지훈", "text": "괜찮아요."}]


def _settings(tmp_path, **kw) -> Settings:
    # 숫자 계산이 기본값 조정에 흔들리지 않게 여유·시작 지연을 고정한다.
    kw = {"edit_tail_seconds": 0.35, "narration_delay_ms": 150, **kw}
    return Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0, **kw)


def _sb(plan):
    """plan: (길이, 종류) 목록. 종류는 "n"(나레이션) / "s"(무음) / "d"(대사)."""
    payload = fake.demo_storyboard_payload(len(plan))
    for cut, (seconds, kind) in zip(payload["cuts"], plan):
        cut["duration_seconds"] = seconds
        if kind == "s":
            cut["narration"] = ""
        elif kind == "d":
            cut["narration"], cut["dialogue"] = "", LINE
    return _StoryboardDraft.model_validate(payload).to_storyboard()


def _wav(path, seconds, rate=24_000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * int(rate * seconds))
    return path


# --- 정적 자르기 ---------------------------------------------------------------


def test_cuts_end_shortly_after_the_voice_but_silent_and_hold_cuts_stay(tmp_path):
    sb = _sb([(6, "n"), (4, "s"), (6, "n"), (8, "n")])
    narr = {i: _wav(tmp_path / f"n{i}.wav", 2.0) for i in (1, 3, 4)}
    lengths = edit_lengths(sb, settings=_settings(tmp_path), narrations=narr, voice_of={},
                           hold={3}, delay=0.15)
    # 나레이션 컷: 0.15 + 2.0 + 0.35 = 2.5초. 무음 컷(동작)과 hold 컷은 그대로.
    assert lengths == [2.5, 4.0, 6.0, 2.5]


def test_short_voice_keeps_minimum_and_last_shot(tmp_path):
    sb = _sb([(6, "n"), (8, "n")])
    sb.cuts[1].shots = [Shot(seconds=3, framing="wide", view="a"), Shot(seconds=3, framing="medium", view="b"),
                        Shot(seconds=2, framing="insert", view="hands")]
    narr = {1: _wav(tmp_path / "a.wav", 0.5), 2: _wav(tmp_path / "b.wav", 2.7)}
    lengths = edit_lengths(sb, settings=_settings(tmp_path), narrations=narr, voice_of={}, hold=set(), delay=0.15)
    assert lengths[0] == 2.2  # 최소 길이
    # 목소리 끝 3.2초: 3초에 시작한 둘째 샷은 1.5초 보여주고(4.5초), 셋째 샷은 버린다.
    assert lengths[1] == 4.5


def test_tight_edit_off_keeps_full_cuts(tmp_path):
    sb = _sb([(6, "n"), (4, "n")])
    narr = {i: _wav(tmp_path / f"n{i}.wav", 1.0) for i in (1, 2)}
    lengths = edit_lengths(sb, settings=_settings(tmp_path, tight_edit=False), narrations=narr,
                           voice_of={}, hold=set(), delay=0.4)
    assert lengths == [6.0, 4.0]


def _probe_seconds(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


@needs_ffmpeg
def test_dummy_pipeline_cuts_dead_air(tmp_path, monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)
    settings = _settings(tmp_path, min_cuts=3, min_total_seconds=4)
    pipe = Pipeline(providers=build_fake_providers(settings), job=JobStore(settings.jobs_dir, "tight"),
                    settings=settings)

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        return sb, await pipe.finish(sb)

    sb, final = asyncio.run(run())
    # 가짜 나레이션 3초 → 컷마다 3.5초. 컷 길이 그대로였다면 sb.final_seconds.
    assert _probe_seconds(final) == pytest.approx(3 * 3.5 - 0.3 * 2, abs=0.15)
    assert _probe_seconds(final) < sb.final_seconds - 1
    # 더미 모드는 편집 계획 LLM을 부르지 않는다 — 음악 없음.
    assert load_plan(pipe.job) == EditPlan()


# --- 편집 계획·배경음악 ------------------------------------------------------------


def test_plan_drops_bad_cut_numbers_and_overlapping_music():
    sb = _sb([(4, "n")] * 6)
    plan = EditPlan(
        hold_cuts=[2, 99],
        music=[MusicCue(from_cut=4, to_cut=6, prompt="b"), MusicCue(from_cut=1, to_cut=3, prompt="a"),
               MusicCue(from_cut=3, to_cut=5, prompt="겹침"), MusicCue(from_cut=5, to_cut=9, prompt="없는 컷")],
    ).checked(sb)
    assert plan.hold_cuts == [2]
    assert [(m.from_cut, m.to_cut) for m in plan.music] == [(1, 3), (4, 6)]


class _PlanLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def complete_json(self, *, system, user, schema):
        self.calls += 1
        raw = json.dumps(self.payload, ensure_ascii=False)
        return schema.model_validate_json(raw), LLMResult(raw_json=raw)


def test_plan_edit_asks_llm_once_and_caches(tmp_path):
    from app.videomake.prompts import get_prompts

    sb = _sb([(4, "n"), (4, "s"), (6, "n")])
    llm = _PlanLLM({"reason": "마무리가 슬프다", "hold_cuts": [3],
                    "music": [{"from_cut": 2, "to_cut": 3, "prompt": "soft piano"}]})
    job = JobStore(tmp_path / "jobs", "plan")
    settings = _settings(tmp_path, dummy=False)
    plan = asyncio.run(plan_edit(sb, llm=llm, prompts=get_prompts(), settings=settings, job=job))
    again = asyncio.run(plan_edit(sb, llm=llm, prompts=get_prompts(), settings=settings, job=job))
    assert plan.hold_cuts == [3] and plan.music[0].prompt == "soft piano"
    assert again == plan and llm.calls == 1


def test_music_off_means_no_cues(tmp_path):
    from app.videomake.prompts import get_prompts

    sb = _sb([(4, "n"), (6, "n")])
    llm = _PlanLLM({"reason": "", "hold_cuts": [], "music": [{"from_cut": 1, "to_cut": 2, "prompt": "x"}]})
    plan = asyncio.run(plan_edit(sb, llm=llm, prompts=get_prompts(), settings=_settings(tmp_path, dummy=False, music=False),
                                 job=JobStore(tmp_path / "jobs", "m")))
    assert plan.music == []


def test_plan_failure_falls_back_to_empty_plan(tmp_path):
    from app.videomake.prompts import get_prompts

    sb = _sb([(4, "n"), (6, "n")])
    # 스토리보드를 돌려주는 가짜 LLM — 편집 계획 스키마와 맞지 않아 실패한다.
    plan = asyncio.run(plan_edit(sb, llm=fake.FakeLLM(2), prompts=get_prompts(),
                                 settings=_settings(tmp_path, dummy=False), job=JobStore(tmp_path / "jobs", "f")))
    assert plan == EditPlan()


@needs_ffmpeg
def test_music_is_made_per_cue_and_fitted_to_its_span(tmp_path):
    job = JobStore(tmp_path / "jobs", "music")
    plan = EditPlan(music=[MusicCue(from_cut=1, to_cut=2, prompt="soft piano")])
    music = fake.FakeMusic()
    files = asyncio.run(make_music(plan, music=music, job=job))
    assert list(files) == [0] and music.prompts == ["soft piano"]
    track = tmp_path / "m.wav"
    _music_track(files[0], track, seconds=47.5)  # 30초 곡을 이어 붙여 47.5초
    assert _probe_seconds(track) == pytest.approx(47.5, abs=0.1)


# --- 나레이션 말투·목소리 ----------------------------------------------------------


def test_spoken_haeyo_and_comma_continuation_pass_lint():
    for text in ["팀장님이 민지 기획서를 그대로 읽더라고요.", "회의 끝나고 조심스럽게 물어봤더니,", "커피로 겨우 진정했는데요,"]:
        assert "해요체로 쓴다" not in [v.rule for v in lint_narration(text, "민지", 6)]
    for text in ["새치기에 발 밟히고 사과도 못 받음.", "민지는 발을 밟혔다."]:
        assert "해요체로 쓴다" in [v.rule for v in lint_narration(text, "민지", 6)]


def test_planner_asks_for_spoken_haeyo_starting_with_name():
    from app.videomake.prompts import get_prompts
    from app.videomake.stages.storyboard import system_prompt

    system = system_prompt(get_prompts(), Settings(_env_file=None))
    assert "친구에게 오늘 일을 들려주듯" in system
    assert '"민지, 출근길부터 …"처럼 이름을 부르듯 쓰지 않는다' in system


def test_fish_needs_a_key_otherwise_gemini_reads(tmp_path):
    gemini = fake.FakeTTS()
    key = {"FISH_API_KEY": "k"}  # .env와 같은 이름으로 넣는다
    assert build_narration_tts(_settings(tmp_path), gemini) is None
    assert build_narration_tts(_settings(tmp_path, narration_tts="gemini", **key), gemini) is None
    assert isinstance(build_narration_tts(_settings(tmp_path, **key), gemini), FallbackTTS)


def test_fallback_reads_with_second_voice_when_first_fails(tmp_path):
    class Broken:
        async def synthesize(self, **kw):
            raise RuntimeError("Fish 429")

    tts = FallbackTTS(Broken(), fake.FakeTTS(seconds=1.0))
    result = asyncio.run(tts.synthesize(text="안녕", dest=tmp_path / "n.wav", voice="Autonoe", style_prompt=""))
    assert result.duration_s == 1.0 and (tmp_path / "n.wav").exists()


def test_fish_price_counts_utf8_bytes():
    assert fish_price("s2.1-pro-free", 600) == 0
    assert fish_price("s2.1-pro", 1_000_000) == Decimal("15")
    assert fish_price("s2.1-pro", 600) == Decimal("0.009")  # 한글 200자 ≈ 1센트


def test_fish_take_that_runs_long_is_retried_then_falls_back(tmp_path, monkeypatch):
    from app.videomake.providers import fish_tts

    takes = iter([9.0, 1.5])  # 첫 번째는 없는 말을 붙여 9초, 두 번째는 정상

    async def fake_call(self, text):
        return b"RIFF"

    def fake_to_wav(src, dest):
        _wav(dest, next(takes))

    monkeypatch.setattr(fish_tts.FishTTSProvider, "_call", fake_call)
    monkeypatch.setattr(fish_tts, "_to_wav", fake_to_wav)
    fish = fish_tts.FishTTSProvider(api_key="k", model="s2.1-pro-free", voice_id="v")
    result = asyncio.run(fish.synthesize(text="커피로 겨우 진정했는데요,", dest=tmp_path / "n.wav", voice="", style_prompt=""))
    assert result.duration_s == 1.5

    takes = iter([9.0, 9.0, 9.0])
    tts = FallbackTTS(fish, fake.FakeTTS(seconds=1.0))
    result = asyncio.run(tts.synthesize(text="짧은 문장", dest=tmp_path / "m.wav", voice="", style_prompt=""))
    assert result.duration_s == 1.0  # 세 번 모두 길어 예비 목소리로


def test_default_pause_after_voice_is_relaxed():
    s = Settings(_env_file=None)
    assert s.edit_tail_seconds == 1.1 and s.narration_delay_ms == 300
