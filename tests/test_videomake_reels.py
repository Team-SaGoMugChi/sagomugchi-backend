"""릴스 스타일 — 무음 컷, 무음 컷까지 이어지는 나레이션, 컷 크로스페이드. 비용 0."""

import asyncio
import json
import shutil
import subprocess

import pytest

from app.videomake.config import CROSSFADE_SECONDS, Settings
from app.videomake.guardrails import lint_storyboard
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.registry import build_fake_providers
from app.videomake.stages.compose import cut_starts
from app.videomake.stages.storyboard import _StoryboardDraft, system_prompt

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")

LINE = [{"speaker": "지훈", "text": "괜찮아?"}, {"speaker": "지훈", "text": "응, 괜찮아."}]


def _payload(plan):
    """plan: (길이, 종류) 목록. 종류는 "n"(나레이션) / "s"(무음) / "d"(대사)."""
    payload = fake.demo_storyboard_payload(len(plan))
    for cut, (seconds, kind) in zip(payload["cuts"], plan):
        cut["duration_seconds"] = seconds
        if kind == "s":
            cut["narration"] = ""
        elif kind == "d":
            cut["narration"], cut["dialogue"] = "", LINE
    return payload


def _sb(plan, narrations=None):
    payload = _payload(plan)
    for pos, text in (narrations or {}).items():
        payload["cuts"][pos - 1]["narration"] = text
    return _StoryboardDraft.model_validate(payload).to_storyboard()


def _rules(sb):
    return [v.rule for v in lint_storyboard(sb)]


def test_narration_runs_over_following_silent_cuts_and_stops_at_dialogue():
    sb = _sb([(4, "n"), (4, "s"), (4, "s"), (6, "d"), (4, "n"), (4, "s")])

    windows = sb.narration_windows()

    x = CROSSFADE_SECONDS
    assert windows[1] == pytest.approx(12 - 3 * x)  # 1~3번 컷, 대사 컷 전에 끝난다
    assert windows[5] == pytest.approx(8 - 2 * x)
    assert set(windows) == {1, 5}  # 무음·대사 컷은 나레이션 구간이 없다


def test_spanning_narration_may_be_longer_than_one_cut():
    long = "도시락을 열자마자 웃음이 났어요. 오랜만에 맛있었어요."  # 31자
    sb = _sb([(4, "n"), (4, "s"), (4, "n")], {1: long})
    assert not any("자 이내" in r for r in _rules(sb))

    alone = _sb([(4, "n"), (4, "n"), (4, "n")], {1: long})
    assert any("자 이내" in r for r in _rules(alone))


def test_first_cut_must_speak():
    sb = _sb([(4, "s"), (4, "n"), (4, "n")])
    assert "첫 컷은 나레이션으로 시작한다" in _rules(sb)


def test_three_silent_cuts_in_a_row_are_fed_back():
    ok = _sb([(4, "n"), (4, "s"), (4, "s"), (4, "n")])
    assert not any("연달아" in r for r in _rules(ok))

    too_many = _sb([(4, "n"), (4, "s"), (4, "s"), (4, "s"), (4, "n")])
    assert "무음 컷은 2개까지 연달아" in _rules(too_many)


def test_silent_cut_is_four_seconds():
    sb = _sb([(4, "n"), (6, "s"), (4, "n")])
    assert "무음 컷은 4초" in _rules(sb)


def test_cut_starts_overlap_by_the_crossfade():
    assert cut_starts([4, 4, 6], crossfade=0.3) == [0.0, 3.7, 7.4]


def test_prompt_asks_for_reels_rhythm_and_varied_camera():
    system = system_prompt(get_prompts(), Settings(_env_file=None))

    assert "릴스·쇼츠처럼 짧은 컷으로" in system
    assert "많아야 하나" in system
    assert "### 무음 컷" in system
    assert "바라보는 쪽을 매번 바꾼다" in system
    assert "### cast" in system
    assert "4초 나레이션 컷 뒤에 4초 무음 컷이 하나 이어지면 33자" in system


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    return float(data["format"]["duration"]), sorted(s["codec_type"] for s in data["streams"])


@needs_ffmpeg
def test_pipeline_with_silent_and_dialogue_cuts_makes_one_crossfaded_video(tmp_path, monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0)
    base = build_fake_providers(settings)
    llm = fake.FakeLLM(4)
    llm.payload = _payload([(4, "n"), (4, "s"), (6, "d"), (4, "n")])
    providers = base.__class__(**{**base.__dict__, "llm": llm})
    pipe = Pipeline(providers=providers, job=JobStore(settings.jobs_dir, "reels"), settings=settings)

    async def run():
        sb = await pipe.run_to_gate(DiaryInput(text="일기"))
        pipe.approve(sb)
        return sb, await pipe.finish(sb)

    sb, final = asyncio.run(run())

    duration, streams = _probe(final)
    assert duration == pytest.approx(sb.final_seconds, abs=0.15)  # 18 - 0.3 × 3 = 17.1
    assert streams == ["audio", "video"]
    # 무음 컷·대사 컷은 나레이션을 만들지 않는다.
    assert sorted(p.parent.name for p in (pipe.job.dir / "cuts").glob("*/narration.wav")) == ["01", "04"]
