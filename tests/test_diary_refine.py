import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.diary_interview import InterviewMessage
from app.services import diary_refine


client = TestClient(app)

FIX_HEADER = "[꼭 고칠 것]"

CONVERSATION = [
    {"speaker": "oddo", "text": "오늘 어떤 일이 있었는지 이야기해줄래요?"},
    {"speaker": "user", "text": "음 오늘 팀 회의에서 제 의견이 그 그냥 무시당했어요."},
    {"speaker": "oddo", "text": "어디였어요?"},
    {"speaker": "user", "text": "스터디룸이요."},
    {"speaker": "oddo", "text": "혹시 더 하고 싶은 이야기가 있어요?"},
    {"speaker": "user", "text": "없어요."},
]


def _fake_chat(monkeypatch, *responses):
    """호출 순서대로 응답을 돌려준다. 호출 내용은 calls에 쌓인다."""
    captured = {"calls": []}
    remaining = list(responses)

    def chat(system_prompt, messages, **kwargs):
        captured["system_prompt"] = system_prompt
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        captured["calls"].append({"system_prompt": system_prompt, "content": messages[0]["content"]})
        response = remaining.pop(0) if len(remaining) > 1 else remaining[0]
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
    conversation = captured["calls"][0]["content"]
    # 짧은 답을 문장으로 만들려면 탄카츄의 질문도 맥락으로 필요하다.
    assert "탄카츄: 어디였어요?" in conversation
    assert "사용자: 스터디룸이요." in conversation


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


def test_refine_asks_for_facts_first_and_returns_only_the_diary(monkeypatch):
    captured = _fake_chat(
        monkeypatch,
        '{"facts": ["회의에서 의견이 무시당함"], "feelings": [], "diary": "회의에서 내 의견이 무시당했다."}',
    )

    response = _post()

    assert response.json() == {"diary": "회의에서 내 의견이 무시당했다."}
    assert captured["kwargs"]["json_mode"] is True
    assert '"facts"' in diary_refine.SYSTEM_PROMPT and '"feelings"' in diary_refine.SYSTEM_PROMPT


def _said(*answers):
    return [InterviewMessage(speaker="user", text=answer) for answer in answers]


def test_refine_polishes_the_draft_as_a_second_step(monkeypatch):
    captured = _fake_chat(
        monkeypatch,
        '{"diary": "시험공부도 막막하고 친구들 부럽고 했다."}',
        '{"diary": "시험공부는 막막했고, 친구들이 부러웠다."}',
    )

    diary = diary_refine.refine_diary(_said("시험공부도 막막하고 친구들 부럽고 그래."))

    assert diary == "시험공부는 막막했고, 친구들이 부러웠다."
    assert [call["system_prompt"] for call in captured["calls"]] == [
        diary_refine.SYSTEM_PROMPT,
        diary_refine.POLISH_PROMPT,
    ]
    assert "시험공부도 막막하고 친구들 부럽고 했다." in captured["calls"][1]["content"]
    assert FIX_HEADER not in captured["calls"][1]["content"]


def test_refine_tells_the_polish_step_about_a_missing_feeling(monkeypatch):
    captured = _fake_chat(
        monkeypatch,
        '{"diary": "노트북이 연결되지 않았다. 답답했다."}',
        '{"diary": "노트북이 연결되지 않았다. 착잡하고 답답했다."}',
    )

    diary = diary_refine.refine_diary(_said("노트북이 연결이 안 됐어.", "그냥 뭐 착잡하고 답답했지."))

    assert diary == "노트북이 연결되지 않았다. 착잡하고 답답했다."
    polish = captured["calls"][1]["content"]
    assert FIX_HEADER in polish
    assert "착잡" in polish


def test_refine_does_not_treat_another_form_of_a_feeling_as_missing(monkeypatch):
    captured = _fake_chat(monkeypatch, '{"diary": "슬프고 진짜 고마웠다."}')

    diary_refine.refine_diary(_said("슬펐어.", "진짜 고맙더라."))

    assert FIX_HEADER not in captured["calls"][1]["content"]


@pytest.mark.parametrize(
    "repeated",
    [
        "노트북이 5분 넘게 연결이 안 됐다. 그래서 노트북이 5분 넘게 연결이 안 됐다.",
        "지금은 화가 가라앉았고, 민수에게 연락해야 하나 고민된다. 지금 화는 가라앉았고, 사과를 받고 싶다.",
    ],
)
def test_refine_tells_the_polish_step_when_content_repeats(monkeypatch, repeated):
    captured = _fake_chat(monkeypatch, f'{{"diary": "{repeated}"}}')

    diary_refine.refine_diary(_said("오늘 일이야."))

    assert "되풀이" in captured["calls"][1]["content"]


def test_refine_does_not_flag_different_sentences_as_repeated(monkeypatch):
    captured = _fake_chat(
        monkeypatch,
        '{"diary": "오늘 오후에 카페에서 친구를 만났다. 저녁에는 집에서 영화를 봤다."}',
    )

    diary_refine.refine_diary(_said("친구 만나고 영화 봤어."))

    assert FIX_HEADER not in captured["calls"][1]["content"]


def test_refine_tells_the_polish_step_about_a_spoken_ending(monkeypatch):
    captured = _fake_chat(monkeypatch, '{"diary": "회의를 했다. 너무 화가 났어."}', '{"diary": "회의를 했다. 너무 화가 났다."}')

    assert diary_refine.refine_diary(_said("회의했는데 너무 화가 났어.")) == "회의를 했다. 너무 화가 났다."
    assert "일기체" in captured["calls"][1]["content"]


@pytest.mark.parametrize(
    "polished",
    [
        RuntimeError("LLM down"),
        '{"diary": ""}',
        "{",
        '{"diary": "노트북이 안 됐어."}',  # 문제가 늘었다
        '{"diary": "노트북이 연결되지 않아서 슬펐다."}',  # 말하지 않은 감정을 지어냈다
        '{"diary": "안 됐다."}',  # 내용까지 줄였다
    ],
)
def test_refine_keeps_the_draft_unless_polishing_is_safe(monkeypatch, polished):
    _fake_chat(monkeypatch, '{"diary": "노트북이 연결되지 않았다."}', polished)

    diary = diary_refine.refine_diary(_said("노트북이 안 돼서 답답했어."))

    assert diary == "노트북이 연결되지 않았다."


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
