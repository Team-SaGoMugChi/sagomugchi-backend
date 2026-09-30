import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import diary_refine


client = TestClient(app)

CONVERSATION = [
    {"speaker": "oddo", "text": "오늘 어떤 일이 있었는지 이야기해줄래요?"},
    {"speaker": "user", "text": "음 오늘 팀 회의에서 제 의견이 그 그냥 무시당했어요."},
    {"speaker": "oddo", "text": "어디였어요?"},
    {"speaker": "user", "text": "스터디룸이요."},
    {"speaker": "oddo", "text": "혹시 더 하고 싶은 이야기가 있어요?"},
    {"speaker": "user", "text": "없어요."},
]


def _fake_chat(monkeypatch, response):
    captured = {}

    def chat(system_prompt, messages, **kwargs):
        captured["system_prompt"] = system_prompt
        captured["messages"] = messages
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("app.services.diary_refine.llm_client.chat", chat)
    return captured


def _post(messages=CONVERSATION):
    return client.post("/diary/interview/refine", json={"messages": messages})


def test_refine_returns_the_diary_and_sends_the_whole_conversation(monkeypatch):
    captured = _fake_chat(
        monkeypatch,
        '{"diary": "오늘 팀 회의에서 내 의견이 무시당했다. 학교 스터디룸에서였다."}',
    )

    response = _post()

    assert response.status_code == 200
    assert response.json() == {"diary": "오늘 팀 회의에서 내 의견이 무시당했다. 학교 스터디룸에서였다."}
    [message] = captured["messages"]
    # 짧은 답을 문장으로 만들려면 탄카츄의 질문도 맥락으로 필요하다.
    assert "탄카츄: 어디였어요?" in message["content"]
    assert "사용자: 스터디룸이요." in message["content"]


def test_refine_prompt_keeps_the_team_rules():
    prompt = diary_refine.SYSTEM_PROMPT
    for rule in (
        "1인칭 유지",
        "말한 내용만 쓸 것 (해석/조언/추가 금지)",
        "감정 표현은 원래 단어 그대로",
        "군더더기/반복/말 더듬기만 정리하고 문장으로 이어 붙이기",
        "일기체(~했다)",
        "요약하지 않는다",
    ):
        assert rule in prompt


def test_refine_accepts_a_plain_text_diary(monkeypatch):
    _fake_chat(monkeypatch, "```\n오늘 팀 회의에서 내 의견이 무시당했다.\n```")

    assert _post().json() == {"diary": "오늘 팀 회의에서 내 의견이 무시당했다."}


@pytest.mark.parametrize(
    "response",
    [RuntimeError("LLM_API_KEY가 설정되지 않았습니다"), '{"diary": "오늘', '{"diary": "  "}', ""],
)
def test_refine_returns_null_when_the_llm_fails(monkeypatch, response):
    _fake_chat(monkeypatch, response)

    body = _post()

    assert body.status_code == 200
    assert body.json() == {"diary": None}


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"speaker": "oddo", "text": "오늘 어떤 일이 있었어요?"}],
        [{"speaker": "counselor", "text": "안녕"}],
    ],
)
def test_refine_rejects_a_conversation_without_user_messages(messages):
    assert _post(messages).status_code == 422
