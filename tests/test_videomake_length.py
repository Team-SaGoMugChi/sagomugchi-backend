"""영상 길이 가변화 — 컷 수(3~10)·컷 길이(4/6/8초)·전체 길이(12~40초)를 LLM이 정한다.

LLM은 가짜라 비용 0.
"""

import asyncio

import pytest
from pydantic import ValidationError

from app.services.video_job import VideoJobManager
from app.videomake.config import Settings
from app.videomake.guardrails import lint_cut
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


# 8초 컷에 맞는 분량(4초 상한 14자를 넘고 8초 상한 34자 안).
LONG_NARRATION = "그는 노트를 덮고 창밖을 한참 바라봤어요."


def _payload(seconds: list[int]) -> dict:
    payload = fake.demo_storyboard_payload(len(seconds))
    for cut, s in zip(payload["cuts"], seconds):
        cut["duration_seconds"] = s
        if s == 8:
            cut["narration"] = LONG_NARRATION
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


@pytest.mark.parametrize(("seconds", "limit"), [(4, 14), (6, 24), (8, 34)])
def test_narration_limit_follows_cut_length(seconds, limit):
    """무음 컷이 뒤따르지 않으면 그 컷 길이(크로스페이드만큼 빼고)가 나레이션 구간이다."""
    def too_long(text):
        cut = Cut(index=1, image_prompt="i", motion_prompt="m", narration=text,
                  duration_seconds=seconds)
        return [v for v in lint_cut(cut, "지훈") if v.field.endswith("narration") and "자 이내" in v.rule]

    assert too_long("가" * (limit - 1) + "요") == []
    assert too_long("가" * limit + "요")


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
    assert "4초 14자 / 6초 24자 / 8초 34자" in system
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


def test_eight_second_cut_with_four_second_narration_is_fed_back():
    padded = _payload([4, 4, 8])
    padded["cuts"][2]["narration"] = "민수는 웃으며 집에 갔어요"  # 14자 — 4초(14자)면 된다
    sb, llm = _plan(padded, _payload([4, 4, 4]))

    assert sb.total_seconds == 12
    assert "8초 컷인데 나레이션이 14자로 4초 상한(14자) 안이다" in llm.users[1]


def test_near_cap_lists_cuts_that_four_seconds_would_fit():
    near_cap = _payload([6, 6, 6, 6, 6, 6])  # 36초, 나레이션은 모두 14자 이하
    sb, llm = _plan(near_cap, _payload([4, 4, 6, 4]))

    assert sb.total_seconds == 18
    assert "전체 길이가 36초로 상한에 가깝다. 컷 1·2·3·4·5·6은" in llm.users[1]


def test_near_cap_is_fine_when_cuts_need_their_length():
    near_cap = _payload([6, 6, 6, 6, 6, 6])
    for cut in near_cap["cuts"]:
        cut["narration"] = "그는 노트를 덮고 숨을 골랐어요."  # 18자 — 4초 상한을 넘는다
    sb, llm = _plan(near_cap)

    assert sb.total_seconds == 36
    assert len(llm.users) == 1


def test_last_cut_does_not_have_to_be_wide():
    payload = _payload([4, 4, 4])
    payload["cuts"][-1]["camera_distance"] = "medium"
    sb, llm = _plan(payload)

    assert sb.cuts[-1].camera_distance == "medium"
    assert len(llm.users) == 1


def test_prompt_ties_length_to_content_and_ending_to_last_emotion():
    _, llm = _plan(_payload([4, 4, 4]))
    system = llm.systems[0]

    assert "상한은 목표가 아니다" in system
    assert "**4초(기본)**: 대부분의 컷" in system
    assert "일기의 마지막 감정" in system
    assert "가장 넓은 샷" not in system
