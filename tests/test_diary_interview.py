import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import diary_interview


client = TestClient(app)

OPENING = {"speaker": "oddo", "text": "오늘 어떤 일이 있었는지 이야기해줄래요?"}
STORY = {"speaker": "user", "text": "오늘 오후 팀 회의에서 제 의견이 무시당했어요."}
ALL_FILLED = {
    "무엇을": "팀 회의에서 의견이 무시당함",
    "언제": "오늘 오후",
    "어디서": "학교 스터디룸",
    "누가": "팀원 네 명",
    "어떻게": "팀장이 바로 다른 얘기로 넘어감",
    "왜": "시간이 없어서",
}


def _llm_json(reply, **slots):
    return json.dumps({"slots": slots, "reply": reply}, ensure_ascii=False)


def _fake_chat(monkeypatch, response):
    captured = {}

    def chat(system_prompt, messages, **kwargs):
        captured["system_prompt"] = system_prompt
        captured["messages"] = messages
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("app.services.diary_interview.llm_client.chat", chat)
    return captured


def _post(user_text=STORY["text"], history=(OPENING,)):
    return client.post(
        "/diary/interview/turn", json={"user_text": user_text, "history": list(history)}
    )


def _history_with_follow_ups(count):
    history = [OPENING, STORY]
    for i in range(count):
        history += [{"speaker": "oddo", "text": f"질문 {i}?"}, {"speaker": "user", "text": "네."}]
    history.pop()  # 마지막 답은 이번 user_text로 보낸다
    return history


def test_interview_turn_fills_slots_and_asks_about_a_missing_one(monkeypatch):
    captured = _fake_chat(
        monkeypatch,
        _llm_json(
            "회의에서 의견이 묻혔군요. 그 회의는 어디에서 있었어요?",
            무엇을="팀 회의에서 의견이 무시당함",
            언제="오늘 오후",
        ),
    )

    response = _post()

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "회의에서 의견이 묻혔군요. 그 회의는 어디에서 있었어요?"
    assert body["done"] is False
    assert body["crisis"] is False
    assert body["slots"]["언제"] == "오늘 오후"
    assert body["slots"]["어디서"] is None
    assert body["missing"] == ["어디서", "누가", "어떻게", "왜"]

    assert "얼마나 지났는지" in captured["system_prompt"]
    # 대화는 역할별 메시지가 아니라 요청 하나에 담는다 — 그래야 JSON 지시를 따른다.
    [message] = captured["messages"]
    assert message["role"] == "user"
    assert f"탄카츄: {OPENING['text']}" in message["content"]
    assert f"사용자: {STORY['text']}" in message["content"]
    assert f"[남은 질문 수] {diary_interview.MAX_FOLLOW_UPS}" in message["content"]


def test_interview_turn_is_done_when_every_slot_is_filled(monkeypatch):
    _fake_chat(monkeypatch, _llm_json("회의 이야기 들려줘서 고마워요.", **ALL_FILLED))

    body = _post(user_text="시간이 없어서 그랬던 것 같아요.").json()

    assert body["done"] is True
    assert body["missing"] == []
    assert body["reply"] == "회의 이야기 들려줘서 고마워요."


def test_interview_turn_does_not_ask_again_once_slots_are_full(monkeypatch):
    _fake_chat(monkeypatch, _llm_json("그 뒤로는 어떻게 됐어요?", **ALL_FILLED))

    body = _post().json()

    assert body["done"] is True
    assert body["reply"] == diary_interview.CLOSING


def test_interview_turn_asks_the_missing_slot_when_llm_closes_early(monkeypatch):
    _fake_chat(monkeypatch, _llm_json("이야기해줘서 고마워요.", 무엇을="회의", 언제="오늘 오후"))

    body = _post().json()

    assert body["done"] is False
    assert body["reply"] == diary_interview.SLOT_QUESTIONS["어디서"]


def test_interview_turn_counts_remaining_questions_after_opening(monkeypatch):
    captured = _fake_chat(monkeypatch, _llm_json("누구와 함께였어요?", 무엇을="회의"))

    _post(user_text="어제요.", history=_history_with_follow_ups(1))

    assert (
        f"[남은 질문 수] {diary_interview.MAX_FOLLOW_UPS - 1}" in captured["messages"][0]["content"]
    )


@pytest.mark.parametrize(
    "llm_reply, expected",
    [
        ("이야기 들려줘서 고마워요.", "이야기 들려줘서 고마워요."),
        ("그 뒤로는 어떻게 됐어요?", diary_interview.CLOSING),
    ],
)
def test_interview_turn_ends_at_the_question_limit_with_missing_slots(
    monkeypatch, llm_reply, expected
):
    _fake_chat(monkeypatch, _llm_json(llm_reply, 무엇을="회의"))

    body = _post(
        user_text="잘 모르겠어요.",
        history=_history_with_follow_ups(diary_interview.MAX_FOLLOW_UPS),
    ).json()

    assert body["done"] is True
    assert body["reply"] == expected
    assert "어디서" in body["missing"]


def test_interview_turn_uses_plain_text_reply_as_question(monkeypatch):
    _fake_chat(monkeypatch, "회의는 어디에서 있었어요?")

    body = _post().json()

    assert body == {
        "reply": "회의는 어디에서 있었어요?",
        "done": False,
        "crisis": False,
        "slots": {},
        "missing": [],
        "summary": None,
    }


@pytest.mark.parametrize(
    "response",
    [
        RuntimeError("LLM_API_KEY가 설정되지 않았습니다"),
        '{"slots": {}, "reply": "그 회의는',
        '{"slots": {}, "reply": "  "}',
        "",
    ],
)
def test_interview_turn_falls_back_to_fixed_questions(monkeypatch, response):
    _fake_chat(monkeypatch, response)

    first = _post().json()
    second = _post(user_text="어제요.", history=_history_with_follow_ups(1)).json()
    last = _post(
        user_text="어제요.", history=_history_with_follow_ups(diary_interview.MAX_FOLLOW_UPS)
    ).json()

    assert first["reply"] == diary_interview.FALLBACK_QUESTIONS[0]
    assert first["done"] is False
    assert second["reply"] == diary_interview.FALLBACK_QUESTIONS[1]
    assert last == {
        "reply": diary_interview.CLOSING,
        "done": True,
        "crisis": False,
        "slots": {},
        "missing": [],
        "summary": None,
    }


@pytest.mark.parametrize(
    "summary, expected",
    [
        ("  오늘은 팀 회의에서 의견이 무시당한 하루였어요.  ", "오늘은 팀 회의에서 의견이 무시당한 하루였어요."),
        ("   ", None),
        (None, None),
    ],
)
def test_interview_turn_returns_the_diary_summary(monkeypatch, summary, expected):
    _fake_chat(
        monkeypatch,
        json.dumps(
            {"slots": {"무엇을": "회의"}, "summary": summary, "reply": "어디였어요?"},
            ensure_ascii=False,
        ),
    )

    assert _post().json()["summary"] == expected


def test_interview_prompt_keeps_the_summary_to_what_the_user_said():
    prompt = diary_interview.SYSTEM_PROMPT
    assert '"summary"' in prompt
    assert "말하지 않은 감정이나 내용은 넣지 않는다" in prompt


def test_interview_turn_cleans_slot_values(monkeypatch):
    _fake_chat(
        monkeypatch,
        json.dumps(
            {"slots": {"무엇을": "  회의  ", "언제": "   ", "기분": "속상함"}, "reply": "어디였어요?"},
            ensure_ascii=False,
        ),
    )

    slots = _post().json()["slots"]

    assert slots["무엇을"] == "회의"
    assert slots["언제"] is None
    assert set(slots) == set(diary_interview.SLOTS)


def test_interview_turn_stops_on_crisis_without_llm(monkeypatch):
    captured = _fake_chat(monkeypatch, AssertionError("LLM must not be called"))

    body = _post(user_text="요즘은 그냥 죽고 싶다는 생각만 들어요.").json()

    assert body["crisis"] is True
    assert body["done"] is False
    assert "109" in body["reply"]
    assert "messages" not in captured


@pytest.mark.parametrize(
    "payload",
    [
        {"user_text": "   "},
        {"user_text": "안녕", "history": [{"speaker": "counselor", "text": "안녕"}]},
        {"user_text": "안녕", "history": [{"speaker": "oddo", "text": ""}]},
    ],
)
def test_interview_turn_rejects_invalid_payload(payload):
    assert client.post("/diary/interview/turn", json=payload).status_code == 422
