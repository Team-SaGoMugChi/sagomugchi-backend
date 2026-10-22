"""제작팀 모드(작가 → 감독 → 스크립터 → 감독 수정) — 가짜 LLM으로 흐름만 확인. 비용 0."""

import asyncio
import json

from app.videomake.config import Settings
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.base import LLMResult
from app.videomake.providers.registry import build_fake_providers
from app.videomake.stages.film_team import ProductionNotes, Review, ShotPlan, plan_with_team

NOTES = {
    "protagonist_name": "지훈",
    "people": [{"name": "지훈", "role": "주인공", "gender": "man", "on_screen": True}],
    "places": ["회의실"],
    "beats": [{"order": 1, "what_happened": "회의에서 발표했다", "who": ["지훈"], "where": "회의실", "time_of_day": "낮",
               "actual_quote": "", "emotion": "불안", "intensity": 60, "props": ["노트"], "must_show": True}],
    "ending_emotion": "평온", "ending_sentence": "집에 와서 쉬었다.", "tone_warnings": ["발표 문장이 기쁨으로 잡힘"],
}


class _TeamLLM:
    """스키마별로 답한다. 첫 검수는 지적 1건, 두 번째 검수는 승인."""

    def __init__(self):
        self.calls = []
        self.reviews = [
            {"approve": False, "issues": [{"cut": 2, "kind": "연속성", "problem": "노트가 사라짐", "fix": "노트를 든 채로"}]},
            {"approve": True, "issues": []},
        ]

    async def complete_json(self, *, system, user, schema):
        self.calls.append((schema.__name__, user))
        if schema is ProductionNotes:
            payload = NOTES
        elif schema is Review:
            payload = self.reviews.pop(0)
        elif schema is ShotPlan:
            payload = {"cuts": []}
        else:
            payload = fake.demo_storyboard_payload(3)
        raw = json.dumps(payload, ensure_ascii=False)
        return schema.model_validate_json(raw), LLMResult(raw_json=raw)


def _settings(tmp_path, **kw):
    return Settings(_env_file=None, jobs_dir=tmp_path / "jobs", poll_interval_seconds=0.0, **kw)


def test_team_runs_writer_director_review_and_revision(tmp_path):
    llm = _TeamLLM()
    job = JobStore(tmp_path / "jobs", "team")
    sb = asyncio.run(plan_with_team(DiaryInput(text="회의에서 발표했다."), llm=llm, prompts=get_prompts(),
                                    settings=_settings(tmp_path), job=job))

    order = [name for name, _ in llm.calls]
    assert order == ["ProductionNotes", "_StoryboardDraft", "Review", "_StoryboardDraft", "Review", "ShotPlan"]
    # 감독은 제작 노트를, 수정본은 검수 지적을 받는다.
    assert "## 제작 노트" in llm.calls[1][1] and "회의에서 발표했다" in llm.calls[1][1]
    assert "노트가 사라짐" in llm.calls[3][1]
    files = sorted(p.name for p in (job.dir / "team").iterdir())
    assert files == ["1_writer_notes.json", "2_director_draft.json", "3_review_1.json",
                     "3_review_2.json", "4_director_revision_1.json", "5_cinematographer.json"]
    assert job.storyboard_path.exists() and len(sb.cuts) == 3


def test_planner_setting_switches_to_team(tmp_path, monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)
    settings = _settings(tmp_path, planner="team", min_cuts=1)
    base = build_fake_providers(settings)
    llm = _TeamLLM()
    llm.reviews = [{"approve": True, "issues": []}]
    pipe = Pipeline(providers=base.__class__(**{**base.__dict__, "llm": llm}),
                    job=JobStore(settings.jobs_dir, "p"), settings=settings)
    asyncio.run(pipe.plan(DiaryInput(text="일기")))
    assert [n for n, _ in llm.calls] == ["ProductionNotes", "_StoryboardDraft", "Review", "ShotPlan"]


def test_default_planner_is_single():
    assert Settings(_env_file=None).planner == "single"


def test_failed_revision_keeps_the_last_passing_draft(tmp_path):
    from app.videomake.errors import GuardrailViolation
    from app.videomake.stages import film_team

    llm = _TeamLLM()
    calls = {"n": 0}
    real = film_team.plan_storyboard

    async def flaky(*a, **kw):
        calls["n"] += 1
        if kw.get("initial_feedback"):
            raise GuardrailViolation("규칙 위반")
        return await real(*a, **kw)

    film_team.plan_storyboard = flaky
    try:
        sb = asyncio.run(plan_with_team(DiaryInput(text="일기"), llm=llm, prompts=get_prompts(),
                                        settings=_settings(tmp_path), job=JobStore(tmp_path / "jobs", "t")))
    finally:
        film_team.plan_storyboard = real
    assert len(sb.cuts) == 3 and calls["n"] == 2


def test_reported_speech_turning_point_asks_for_dialogue_cut():
    from app.videomake.stages.film_team import _notes_text

    notes = ProductionNotes.model_validate({**NOTES, "beats": [{**NOTES["beats"][0], "actual_quote": "너무 예민하게 굴지 마."}]})
    text = _notes_text(notes)
    assert '일기 속 말: "너무 예민하게 굴지 마."' in text and "dialogue 컷으로" in text
    assert "dialogue 컷으로" not in _notes_text(ProductionNotes.model_validate(NOTES))


def _sb_with_narration_cut():
    from app.videomake.models import Storyboard

    payload = fake.demo_storyboard_payload(3)
    payload["cuts"][1].update(duration_seconds=6, camera_distance="wide")
    return Storyboard.model_validate(payload)


def test_shot_plan_is_applied_and_first_shot_keeps_the_cut_framing():
    from app.videomake.stages.film_team import apply_shot_plan

    sb = _sb_with_narration_cut()
    plan = ShotPlan.model_validate({"cuts": [
        {"cut": 2, "shots": [{"seconds": 3, "framing": "medium", "view": "the room"},
                             {"seconds": 3, "framing": "insert", "view": "her hands on the cup"}]},
        {"cut": 1, "shots": [{"seconds": 2, "framing": "wide", "view": "x"}, {"seconds": 2, "framing": "wide", "view": "y"}]},
        {"cut": 9, "shots": []},
    ]})
    out, dropped = apply_shot_plan(sb, plan)
    cut2 = out.cuts[1]
    assert [s.framing for s in cut2.shots] == ["wide", "insert"]  # 첫 샷 = 컷 그림의 거리
    assert not out.cuts[0].shots and len(dropped) == 2  # 짧은 컷·없는 컷은 버린다


def test_shots_must_fill_the_cut_and_skip_dialogue():
    import pytest
    from app.videomake.models import Cut

    base = _sb_with_narration_cut().cuts[1].model_dump()
    with pytest.raises(ValueError, match="합"):
        Cut.model_validate({**base, "shots": [{"seconds": 2, "framing": "wide", "view": "a"},
                                              {"seconds": 2, "framing": "medium", "view": "b"}]})


def test_multi_shot_cut_gets_timestamped_video_prompt():
    from app.videomake.models import Shot

    text = get_prompts().render(
        "motion.j2", motion_prompt="She waits.", duration=6, dialogue=[], solo_side=None, ambient=True,
        listening=False, mood_line="m",
        shots=[Shot(seconds=3, framing="wide", view="the cafe"), Shot(seconds=3, framing="insert", view="her phone")])
    assert "[00:00.0-00:03.0] Wide shot exactly as the first frame" in text
    assert "[00:03.0-00:06.0] Hard cut to an insert shot: her phone" in text
    assert "Nobody ever looks into the camera" in text
    assert "exactly 1 cuts" in text and "no cut after 00:03.0" in text
    assert "do not cross the line" in text
    dressed = get_prompts().render(
        "motion.j2", motion_prompt="x", duration=6, dialogue=[], solo_side=None, ambient=True, listening=False,
        mood_line="m", shots=[Shot(seconds=3, framing="wide", view="a"), Shot(seconds=3, framing="medium", view="b")],
        outfits=[{"look": "A woman in a beige trench coat.", "position": "left"}])
    assert "the person on the left side of the first frame stays on that same side" in dressed
    assert "beige trench coat" in dressed
    single = get_prompts().render("motion.j2", motion_prompt="She waits.", duration=6, shots=[], dialogue=[],
                                  solo_side=None, ambient=True, listening=False, mood_line="m")
    assert "constant distance" in single and "Hard cut" not in single
