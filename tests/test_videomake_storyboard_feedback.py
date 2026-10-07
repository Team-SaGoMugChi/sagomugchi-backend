"""스토리보드 재요청 피드백과 영어 프롬프트 가드레일. LLM은 가짜라 비용 0."""

import asyncio

from app.videomake.config import Settings
from app.videomake.guardrails import lint_storyboard
from app.videomake.models import DiaryInput, Storyboard
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.base import LLMResult
from app.videomake.stages.storyboard import _StoryboardDraft, plan_storyboard


class _SequenceLLM:
    """호출마다 준비된 스토리보드를 차례로 돌려주고 받은 user 프롬프트를 남긴다."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.users = []

    async def complete_json(self, *, system, user, schema):
        self.users.append(user)
        payload = self.payloads.pop(0)
        draft = schema.model_validate(payload)
        return draft, LLMResult(raw_json=draft.model_dump_json())


def _payload(n_cuts=3):
    return fake.demo_storyboard_payload(n_cuts)


def _settings():
    return Settings(_env_file=None)


def test_all_cut_errors_are_reported_with_cut_numbers():
    payload = _payload()
    line = {"speaker": "지훈", "text": "괜찮아?"}
    payload["cuts"][0]["dialogue"] = [line, line]  # 나레이션과 대사를 함께 씀
    payload["cuts"][2].update(narration="", dialogue=[line])  # 대사 한 줄뿐
    errors = _StoryboardDraft.model_validate(payload).cut_errors()

    assert len(errors) == 2
    assert errors[0].startswith("cut1") and "함께 넣을 수 없다" in errors[0]
    assert errors[1].startswith("cut3") and "1줄뿐" in errors[1]


def test_cut_index_follows_order_not_llm_value():
    payload = _payload()
    for i, cut in enumerate(payload["cuts"]):
        cut["index"] = i  # 0부터 세는 모델
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()
    assert [c.index for c in sb.cuts] == [1, 2, 3]


def test_retry_feedback_includes_previous_result_and_violations():
    bad = _payload()
    bad["cuts"][1]["narration"] = "그는 노트를 덮었다."  # 해요체가 아니다
    llm = _SequenceLLM([bad, _payload()])

    sb = asyncio.run(
        plan_storyboard(
            DiaryInput(text="일기"), llm=llm, prompts=get_prompts(), settings=_settings()
        )
    )

    assert len(sb.cuts) == 3
    retry = llm.users[1]
    assert "## 직전 결과" in retry
    assert '"image_prompt"' in retry  # 직전 JSON이 들어 있다
    assert "[cut2.narration] 해요체로 쓴다" in retry
    assert "위 항목만 고쳐라" in retry


def _storyboard(**cut_overrides) -> Storyboard:
    payload = _payload()
    payload["cuts"][0].update(cut_overrides)
    return _StoryboardDraft.model_validate(payload).to_storyboard()


def _english_violations(sb):
    return [v for v in lint_storyboard(sb) if v.rule == "영어로 작성"]


def test_korean_image_prompt_is_violation():
    sb = _storyboard(image_prompt="지훈이 회의실에 혼자 앉아 있다. wide shot.")
    violations = _english_violations(sb)
    assert [v.field for v in violations] == ["cut1.image_prompt"]
    assert "회의실에" in violations[0].detail


def test_character_names_in_english_prompt_are_allowed():
    sb = _storyboard(image_prompt="A wide shot of 지훈 sitting alone in a meeting room.")
    assert _english_violations(sb) == []


def test_korean_appearance_is_violation():
    payload = _payload()
    payload["protagonist"]["appearance"] = "짧은 검은 머리"
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()
    assert [v.field for v in _english_violations(sb)] == ["지훈.appearance"]
