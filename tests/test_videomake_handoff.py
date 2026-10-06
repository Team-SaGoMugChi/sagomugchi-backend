"""일기 전달 JSON(handoff)이 영상 스토리보드 프롬프트에 반영되는지. LLM은 가짜라 비용 0."""

import asyncio
import copy

from app.models.video import VideoJobRequest
from app.services.video_job import to_diary_input
from app.videomake.config import Settings
from app.videomake.handoff import diary_text, storyboard_context
from app.videomake.models import DiaryInput
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.base import LLMResult
from app.videomake.stages.storyboard import plan_storyboard

HANDOFF = {
    "설명": {"목적": "필드 설명 — 프롬프트에 넣지 않는다"},
    "schema": "oddo.diary_emotion.v1",
    "diary": {
        "date": "2026-10-02",
        "transcript": "오늘 아침에 팀 회의가 있었어요.\n발표를 했는데 너무 속상했어요.",
        "diary_text": "아침 팀 회의에서 발표를 했는데 지적을 받아 속상했다. 저녁에 친구와 통화하며 나아졌다.",
        "summary": "회의 발표에서 지적을 받아 속상했지만 저녁에 기분이 나아졌다.",
        "slots": {"누가": "나, 팀장님, 친구", "어디서": "회사 회의실", "어떻게": None, "왜": "  "},
    },
    "emotion_overall": {
        "keywords": ["상처"],
        "arc": "부정(상처, 당황) → 긍정(기쁨)",
        "signals": ["평소보다 목소리가 낮고 작았어요"],
        "incongruent": True,
    },
    "scenes": [
        {"order": 1, "tone": "부정", "emotions": ["상처", "당황"], "intensity": 70,
         "text": "발표를 했는데 너무 속상했어요."},
        {"order": 2, "tone": "긍정", "emotions": ["기쁨"], "intensity": 71,
         "text": "저녁에 친구랑 통화하면서 많이 웃었어요."},
    ],
    "turning_points": [{"turn": 3, "from": "부정", "to": "긍정", "sentence": "점심은 혼자 먹었어요."}],
    "sentences": [{"index": 1, "text": "문장별 감정 — 프롬프트에 넣지 않는다"}],
}


class _RecordingLLM:
    def __init__(self):
        self.users = []

    async def complete_json(self, *, system, user, schema):
        self.users.append(user)
        draft = schema.model_validate(fake.demo_storyboard_payload(3))
        return draft, LLMResult(raw_json=draft.model_dump_json())


def _user_prompt(diary: DiaryInput) -> str:
    llm = _RecordingLLM()
    asyncio.run(
        plan_storyboard(diary, llm=llm, prompts=get_prompts(), settings=Settings(_env_file=None))
    )
    return llm.users[0]


def test_job_request_uses_refined_diary_and_keeps_handoff():
    req = VideoJobRequest(text="다듬지 않은 대화 원문", diary_handoff=HANDOFF)
    diary = to_diary_input(req)

    assert diary.text == HANDOFF["diary"]["diary_text"]
    assert diary.handoff == HANDOFF


def test_without_handoff_text_is_used_as_before():
    diary = to_diary_input(VideoJobRequest(text="그냥 평범한 하루였다."))
    assert diary.text == "그냥 평범한 하루였다."
    assert diary.handoff is None


def test_handoff_sections_appear_in_storyboard_prompt():
    user = _user_prompt(DiaryInput(text="일기", handoff=HANDOFF))

    assert "## 일기 기록 자료" in user
    assert "회의 발표에서 지적을 받아 속상했지만" in user
    assert "- 어디서: 회사 회의실" in user
    assert "1. [부정 · 상처, 당황 · 강도 70] 발표를 했는데 너무 속상했어요." in user
    assert "2. [긍정 · 기쁨 · 강도 71] 저녁에 친구랑 통화하면서" in user
    assert '- 부정 → 긍정: "점심은 혼자 먹었어요."' in user
    assert "부정(상처, 당황) → 긍정(기쁨)" in user
    assert "- 평소보다 목소리가 낮고 작았어요" in user
    assert "말한 감정과 표정·목소리가 서로 어긋났다." in user


def test_noise_is_left_out_of_prompt():
    user = _user_prompt(DiaryInput(text="일기", handoff=HANDOFF))

    assert "필드 설명" not in user
    assert "문장별 감정" not in user
    assert "어떻게" not in user  # 말하지 않은 칸
    assert "- 왜:" not in user  # 공백뿐인 칸


def test_prompt_without_handoff_has_no_handoff_section():
    user = _user_prompt(DiaryInput(text="오늘 회의에서 있었던 일"))
    assert "일기 기록 자료" not in user
    assert "오늘 회의에서 있었던 일" in user


def test_unknown_schema_is_ignored():
    other = {**HANDOFF, "schema": "oddo.diary_emotion.v0-sample"}
    assert storyboard_context(other) is None
    assert diary_text(other) is None


def test_broken_fields_are_dropped_not_raised():
    broken = copy.deepcopy(HANDOFF)
    broken["diary"]["slots"] = "칸이 문자열로 옴"
    broken["scenes"] = [{"tone": "부정"}, "장면이 문자열", {"text": "남는 장면", "intensity": "높음"}]
    broken["turning_points"] = None
    broken["emotion_overall"]["signals"] = "문장 하나"

    context = storyboard_context(broken)

    assert context["slots"] == {}
    assert context["scenes"] == [
        {"order": None, "tone": "중립", "emotions": [], "intensity": None, "text": "남는 장면"}
    ]
    assert context["turning_points"] == []
    assert context["signals"] == []
    user = _user_prompt(DiaryInput(text="일기", handoff=broken))
    assert "1. [중립] 남는 장면" in user
