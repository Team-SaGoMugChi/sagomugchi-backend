"""영상 길이 가변화 — 컷 수(3~10)·컷 길이(4/6/8초)·전체 길이(12~40초)를 LLM이 정한다.

LLM은 가짜라 비용 0.
"""

import asyncio

import pytest
from pydantic import ValidationError

from app.services.video_job import VideoJobManager
from app.videomake.config import Settings
from app.videomake.job import JobStore
from app.videomake.models import Cut, DiaryInput
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.base import LLMResult
from app.videomake.stages.storyboard import _StoryboardDraft, plan_storyboard


class _SequenceLLM:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.systems, self.users = [], []

    async def complete_json(self, *, system, user, schema):
        self.systems.append(system)
        self.users.append(user)
        draft = schema.model_validate(self.payloads.pop(0))
        return draft, LLMResult(raw_json=draft.model_dump_json())


def _payload(seconds: list[int]) -> dict:
    payload = fake.demo_storyboard_payload(len(seconds))
    for cut, s in zip(payload["cuts"], seconds):
        cut["duration_seconds"] = s
    return payload


def _plan(*payloads):
    llm = _SequenceLLM(payloads)
    sb = asyncio.run(
        plan_storyboard(
            DiaryInput(text="일기"),
            llm=llm,
            prompts=get_prompts(),
            settings=Settings(_env_file=None),
        )
    )
    return sb, llm


def test_llm_chooses_cut_count_and_each_cut_length():
    sb, llm = _plan(_payload([4, 8, 6, 4]))

    assert [c.duration_seconds for c in sb.cuts] == [4, 8, 6, 4]
    assert sb.total_seconds == 22
    assert len(llm.users) == 1


def test_too_few_cuts_is_fed_back():
    sb, llm = _plan(_payload([8, 8]), _payload([4, 4, 6]))

    assert len(sb.cuts) == 3
    assert "컷이 2개다. 3~10개여야 한다." in llm.users[1]


def test_total_length_over_40_seconds_is_fed_back():
    sb, llm = _plan(_payload([8] * 6), _payload([8, 6, 6, 4]))

    assert sb.total_seconds == 24
    assert "전체 길이가 48초다. 12~40초여야 한다." in llm.users[1]


def test_total_length_under_12_seconds_is_fed_back():
    _, llm = _plan(_payload([4, 4]), _payload([4, 4, 4]))
    assert "전체 길이가 8초다" in llm.users[1]


def test_unsupported_cut_length_is_rejected_by_schema():
    payload = _payload([4, 4, 4])
    payload["cuts"][0]["duration_seconds"] = 5
    with pytest.raises(ValidationError):
        _StoryboardDraft.model_validate(payload)


@pytest.mark.parametrize(("seconds", "limit"), [(4, 14), (6, 21), (8, 28)])
def test_narration_limit_follows_cut_length(seconds, limit):
    Cut(index=1, image_prompt="i", motion_prompt="m", narration="가" * limit,
        duration_seconds=seconds)
    with pytest.raises(ValidationError, match=f"{seconds}초 컷 상한 {limit}자"):
        Cut(index=1, image_prompt="i", motion_prompt="m", narration="가" * (limit + 1),
            duration_seconds=seconds)


def test_dialogue_needs_at_least_six_seconds():
    lines = [{"speaker": "지훈", "text": "괜찮아?"}, {"speaker": "수아", "text": "응."}]
    Cut(index=1, image_prompt="i", motion_prompt="m", dialogue=lines, duration_seconds=6)
    with pytest.raises(ValidationError, match="6초 이상"):
        Cut(index=1, image_prompt="i", motion_prompt="m", dialogue=lines, duration_seconds=4)


def test_prompt_states_length_ranges_and_per_length_limits():
    _, llm = _plan(_payload([4, 4, 4]))
    system = llm.systems[0]

    assert "3~10개" in system
    assert "4 / 6 / 8초 중 하나만" in system
    assert "12~40초" in system
    assert "4초 14자 / 6초 21자 / 8초 28자" in system
    assert "6초 30자 / 8초 40자" in system
    assert "{{" not in system


def test_job_progress_counts_cuts_from_storyboard(tmp_path):
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs")
    manager = VideoJobManager(settings)
    job_id = manager.create()
    job = JobStore(settings.jobs_dir, job_id)
    sb = _StoryboardDraft.model_validate(_payload([4, 4, 4, 4, 4])).to_storyboard()
    job.save_storyboard(sb)
    job.character_sheet_path.write_bytes(b"x")
    for i in range(1, 6):
        job.cut_image(i).write_bytes(b"x")

    stage, progress = manager._progress(job_id)

    # 설정값이 아니라 스토리보드의 컷 5개를 기준으로 이미지 단계가 끝났다고 본다.
    assert (stage, progress) == ("videos", 0.30)
