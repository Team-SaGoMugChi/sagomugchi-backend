import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import diary_interview


client = TestClient(app)

OPENING = {"speaker": "oddo", "text": "오늘 어떤 일이 있었는지 이야기해줄래요?"}
STORY = {"speaker": "user", "text": "오늘 오후 팀 회의에서 제 의견이 무시당했어요."}
# 말이 이어지는 어미로 끝난 발화 — 이때만 맞장구 차례가 된다.
TRAILING = "팀장이 갑자기 다른 얘기를 꺼냈는데"
WRAP_UP_ASKED = {"speaker": "oddo", "text": diary_interview.WRAP_UP}
ALL_FILLED = {
    "무엇을": "팀 회의에서 의견이 무시당함",
    "언제": "오늘 오후",
    "어디서": "학교 스터디룸",
    "누가": "팀원 네 명",
    "어떻게": "팀장이 바로 다른 얘기로 넘어감",
    "왜": "마감이 급해서",
    "그때 기분": "속상했음",
    "기분 변화": "변화 없음",
    "지금 기분": "조금 서운함",
}


def _facts(just_felt=False, finished=False, summary=None, **slots):
    """칸 추출 호출(첫 번째 LLM 호출)의 응답."""
    return json.dumps(
        {"slots": slots, "summary": summary, "just_felt": just_felt, "finished": finished},
        ensure_ascii=False,
    )


def _fake_chat(monkeypatch, *responses):
    """호출 순서대로 응답한다 — 칸 추출, 말 만들기. 응답이 하나면 매번 그걸 쓴다."""
    calls = []

    def chat(system_prompt, messages, **kwargs):
        calls.append({"system_prompt": system_prompt, "messages": messages, **kwargs})
        response = responses[min(len(calls), len(responses)) - 1]
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("app.services.diary_interview.llm_client.chat", chat)
    return calls


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


def _history_after_wrap_up():
    return [OPENING, STORY, {"speaker": "oddo", "text": "어디였어요?"},
            {"speaker": "user", "text": "스터디룸이요."}, WRAP_UP_ASKED]


def _task(calls):
    """말 만들기 호출에 넘긴 [이번에 할 일]."""
    return calls[1]["messages"][0]["content"].split("[이번에 할 일]")[1]


def test_interview_turn_fills_slots_and_asks_about_a_missing_one(monkeypatch):
    calls = _fake_chat(
        monkeypatch,
        _facts(무엇을="팀 회의에서 의견이 무시당함", 언제="오늘 오후"),
        "회의에서 의견이 묻혔군요. 그 회의는 어디에서 있었어요?",
    )

    response = _post()

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "회의에서 의견이 묻혔군요. 그 회의는 어디에서 있었어요?"
    assert body["done"] is False
    assert body["crisis"] is False
    assert body["slots"]["언제"] == "오늘 오후"
    assert body["slots"]["그때 기분"] is None
    assert body["missing"] == [n for n in diary_interview.SLOTS if n not in ("무엇을", "언제")]

    extract, compose = calls
    assert extract["system_prompt"] == diary_interview.EXTRACT_PROMPT
    assert "얼마나 지났는지" in extract["system_prompt"]
    assert extract["json_mode"] is True
    assert extract["temperature"] == 0
    # 대화는 역할별 메시지가 아니라 요청 하나에 담는다 — 그래야 지시를 따른다.
    [message] = extract["messages"]
    assert message["role"] == "user"
    assert f"탄카츄: {OPENING['text']}" in message["content"]
    assert f"사용자: {STORY['text']}" in message["content"]

    assert compose["system_prompt"] == diary_interview.REPLY_PROMPT
    assert "- 언제: 오늘 오후" in compose["messages"][0]["content"]  # 이미 들은 것
    # 빈 칸 중 묻는 순서(ASK_ORDER)의 앞 두 칸이 후보다.
    assert "- 어떻게:" in _task(calls)
    assert "- 그때 기분:" in _task(calls)
    assert "- 누가:" not in _task(calls)


def test_interview_prompts_fill_only_what_the_user_said_and_ask_open_feeling_questions():
    assert "직접 말했을 때만 채운다" in diary_interview.EXTRACT_PROMPT
    for name in diary_interview.FEELING_SLOTS:
        assert name in diary_interview.EXTRACT_PROMPT
    assert "감정 단어를 먼저 제시하지 않는다" in diary_interview.REPLY_PROMPT
    assert "감정을 짐작해 말하지 않는다" in diary_interview.REPLY_PROMPT
    assert "그대로 되풀이하지 않는다" in diary_interview.REPLY_PROMPT


@pytest.mark.parametrize(
    "user_text, last_question",
    [
        ("회의에서 무시당해서 너무 속상했어요.", "무슨 일이 있었어요?"),  # 방금 감정을 말함
        ("팀장이 바로 다른 얘기로 넘어갔어요.", "그때 마음이 어땠어요?"),  # 직전에 기분을 물음
    ],
)
def test_interview_turn_does_not_ask_feelings_twice_in_a_row(monkeypatch, user_text, last_question):
    just_felt = "속상" in user_text
    calls = _fake_chat(
        monkeypatch,
        _facts(just_felt=just_felt, 무엇을="회의", 언제="오늘 오후"),
        "그때 누구랑 있었어요?",
    )

    _post(user_text=user_text, history=[OPENING, STORY, {"speaker": "oddo", "text": last_question}])

    task = _task(calls)
    for name in diary_interview.FEELING_SLOTS:
        assert f"- {name}:" not in task
    assert "- 어떻게:" in task
    assert "- 누가:" in task


def test_interview_turn_never_asks_the_mood_change_directly(monkeypatch):
    # 그때·직후·지금 기분을 세 번 물으면 어색하다 — 기분 변화는 칸 추출이 비교해 채운다.
    assert "기분 변화" not in diary_interview.ASK_ORDER
    filled = {k: v for k, v in ALL_FILLED.items() if k not in ("기분 변화", "지금 기분")}
    calls = _fake_chat(monkeypatch, _facts(**filled), "지금은 좀 어때요?")

    _post(user_text="결국 회의는 그렇게 끝났어요.")

    assert "- 지금 기분:" in _task(calls)
    assert "- 기분 변화:" not in _task(calls)


def test_interview_turn_wraps_up_without_the_mood_change(monkeypatch):
    filled = {k: v for k, v in ALL_FILLED.items() if k != "기분 변화"}
    calls = _fake_chat(monkeypatch, _facts(**filled), "오늘 더 하고 싶은 이야기 있어요?")

    body = _post(user_text="지금은 조금 서운해요.").json()

    assert diary_interview.WRAP_UP_MARK in _task(calls)
    assert body["missing"] == ["기분 변화"]  # 앱에는 그대로 빈 칸으로 알린다
    assert body["done"] is False


def test_interview_turn_listens_when_only_feelings_are_left_but_just_heard_one(monkeypatch):
    filled = {k: v for k, v in ALL_FILLED.items() if k not in ("기분 변화", "지금 기분")}
    calls = _fake_chat(monkeypatch, _facts(just_felt=True, **filled), "아, 속상했군요. 계속 들려줘요.")

    body = _post(user_text="그때 진짜 속상했어요.").json()

    assert "질문하지 않는다" in _task(calls)
    assert body["reply"] == "아, 속상했군요. 계속 들려줘요."
    assert body["done"] is False


@pytest.mark.parametrize("user_text", [TRAILING, "회의가 길어져서", "밥 먹고"])  # "회의실에서"는 아님
def test_interview_turn_listens_while_the_story_trails_on(monkeypatch, user_text):
    calls = _fake_chat(monkeypatch, _facts(무엇을="회의"), "와, 그래서요. 계속 들려줘요.")

    body = _post(user_text=user_text).json()

    assert "질문하지 않는다" in _task(calls)
    assert body["reply"] == "와, 그래서요. 계속 들려줘요."
    assert body["done"] is False


def test_interview_turn_asks_when_the_user_finished_a_short_answer(monkeypatch):
    calls = _fake_chat(monkeypatch, _facts(무엇을="회의", 언제="오늘 오후"), "그래서 어떻게 됐어요?")

    _post(user_text="오늘 오후에 회사 회의실에서.")

    assert "다음 중 이야기 흐름에 맞는 하나" in _task(calls)


@pytest.mark.parametrize(
    "llm_reply, expected",
    [
        ("와, 진짜요. 그래서 어떻게 됐어요?", "와, 진짜요."),
        ("그 뒤엔 어떻게 됐어요?", None),  # 질문뿐이면 고정 맞장구
    ],
)
def test_interview_turn_drops_questions_from_a_listening_turn(monkeypatch, llm_reply, expected):
    _fake_chat(monkeypatch, _facts(무엇을="회의"), llm_reply)

    reply = _post(user_text=TRAILING).json()["reply"]

    if expected is None:
        assert reply in diary_interview.LISTENINGS
    else:
        assert reply == expected


def test_interview_turn_does_not_listen_twice_in_a_row(monkeypatch):
    calls = _fake_chat(monkeypatch, _facts(무엇을="회의"), "그래서 어떻게 됐어요?")

    _post(user_text=TRAILING, history=[OPENING, STORY, {"speaker": "oddo", "text": "와, 계속 들려줘요."}])

    assert "다음 중 이야기 흐름에 맞는 하나" in _task(calls)


def test_interview_turn_asks_to_wrap_up_before_ending_when_slots_are_full(monkeypatch):
    calls = _fake_chat(monkeypatch, _facts(**ALL_FILLED), "마감이 급했군요. 오늘 더 하고 싶은 이야기 있어요?")

    body = _post(user_text="마감이 급해서 그랬던 것 같아요.").json()

    assert diary_interview.WRAP_UP_MARK in _task(calls)
    assert body["done"] is False
    assert body["missing"] == []
    assert body["reply"] == "마감이 급했군요. 오늘 더 하고 싶은 이야기 있어요?"


def test_interview_turn_keeps_listening_when_slots_are_full_but_the_story_goes_on(monkeypatch):
    _fake_chat(monkeypatch, _facts(**ALL_FILLED), "와, 계속 들려줘요.")

    body = _post(user_text=TRAILING).json()

    assert body["done"] is False
    assert body["reply"] == "와, 계속 들려줘요."


@pytest.mark.parametrize(
    "follow_ups, user_text, llm_reply",
    [
        (1, "네.", "이야기해줘서 고마워요."),  # 확인 구절 없이 끝내려 함
        (diary_interview.MAX_FOLLOW_UPS - 1, TRAILING, "그다음엔 어떻게 됐어요?"),  # 질문이 한 번 남음
    ],
)
def test_interview_turn_forces_the_wrap_up_question_when_slots_are_full(
    monkeypatch, follow_ups, user_text, llm_reply
):
    _fake_chat(monkeypatch, _facts(**ALL_FILLED), llm_reply)

    body = _post(user_text=user_text, history=_history_with_follow_ups(follow_ups)).json()

    assert body["done"] is False
    assert body["reply"] == diary_interview.WRAP_UP


@pytest.mark.parametrize(
    "user_text, finished",
    [
        ("없어요.", True),
        ("아니요", True),
        # LLM이 finished를 놓쳐도 짧게 "없다"고 하면 끝낸다.
        ("괜찮아요!", False),
    ],
)
def test_interview_turn_ends_with_a_fixed_closing_after_wrap_up(monkeypatch, user_text, finished):
    # 끝인사가 들은 이야기를 짚으면("회의에서 당황했던 일을 말해줘서 고마워요") 어색하다.
    calls = _fake_chat(monkeypatch, _facts(finished=finished, **ALL_FILLED), AssertionError("no compose"))

    body = _post(user_text=user_text, history=_history_after_wrap_up()).json()

    assert body["done"] is True
    assert body["reply"] in diary_interview.CLOSINGS
    assert len(calls) == 1  # 끝인사는 말 만들기를 부르지 않는다


def test_interview_turn_goes_on_when_the_user_adds_more_after_wrap_up(monkeypatch):
    _fake_chat(monkeypatch, _facts(**ALL_FILLED), "친구한테도 얘기했군요. 계속 들려줘요.")

    body = _post(
        user_text="아 그리고 저녁에 친구한테 이 얘기를 했는데", history=_history_after_wrap_up()
    ).json()

    assert body["done"] is False
    assert body["reply"] == "친구한테도 얘기했군요. 계속 들려줘요."


def test_interview_turn_does_not_end_on_no_without_a_wrap_up_question(monkeypatch):
    _fake_chat(monkeypatch, _facts(finished=True, 무엇을="회의"), "혼자 있었어요?")

    body = _post(user_text="아니요", history=_history_with_follow_ups(1)).json()

    assert body["done"] is False


def test_interview_turn_asks_the_missing_slot_when_the_reply_has_no_question(monkeypatch):
    _fake_chat(monkeypatch, _facts(무엇을="회의", 언제="오늘 오후"), "이야기해줘서 고마워요.")

    body = _post().json()

    assert body["done"] is False
    assert body["reply"] == diary_interview.SLOT_QUESTIONS["어떻게"]


@pytest.mark.parametrize(
    "llm_reply, expected",
    [
        ("정말 속상했겠어요. 그때 누구랑 있었어요?", "그때 누구랑 있었어요?"),
        # 사용자가 말하지 않은 감정 단어 — 짐작("~했군요")과 감정 단어를 넣은 질문
        ("5분이나 안 되다니, 정말 난감했군요. 누구랑 있었어요?", "누구랑 있었어요?"),
        ("의견이 묻혔군요. 속상했어요?", diary_interview.SLOT_QUESTIONS["어떻게"]),
        # 들은 사실을 받는 반응은 그대로 둔다
        ("아, 무시당했군요. 누구랑 있었어요?", "아, 무시당했군요. 누구랑 있었어요?"),
        ("탄카츄: 그래서 어떻게 됐어요?", "그래서 어떻게 됐어요?"),
        ("회의였군요. 그럼, 누구랑 있었어요?", "회의였군요. 누구랑 있었어요?"),
        ("힘들었겠네요.", diary_interview.SLOT_QUESTIONS["어떻게"]),  # 남는 말이 없으면 고정 질문
    ],
)
def test_interview_turn_tidies_the_reply(monkeypatch, llm_reply, expected):
    _fake_chat(monkeypatch, _facts(무엇을="회의", 언제="오늘 오후"), llm_reply)

    assert _post().json()["reply"] == expected


def test_interview_turn_keeps_a_feeling_word_the_user_said_before(monkeypatch):
    _fake_chat(monkeypatch, _facts(무엇을="회의", 언제="오늘 오후"), "그렇게 당황했군요. 누구랑 있었어요?")

    history = [OPENING, {"speaker": "user", "text": "발표하다 너무 당황했어요."},
               {"speaker": "oddo", "text": "언제였어요?"}]
    body = _post(user_text="오늘 오후요.", history=history).json()

    assert body["reply"] == "그렇게 당황했군요. 누구랑 있었어요?"


def test_interview_turn_ends_at_the_question_limit_with_missing_slots(monkeypatch):
    _fake_chat(monkeypatch, _facts(무엇을="회의"), AssertionError("no compose"))

    body = _post(
        user_text="잘 모르겠어요.",
        history=_history_with_follow_ups(diary_interview.MAX_FOLLOW_UPS),
    ).json()

    assert body["done"] is True
    assert body["reply"] in diary_interview.CLOSINGS
    assert "어디서" in body["missing"]


def test_interview_turn_keeps_the_slots_when_only_the_reply_fails(monkeypatch):
    _fake_chat(monkeypatch, _facts(무엇을="회의", 언제="오늘 오후"), RuntimeError("timeout"))

    body = _post().json()

    assert body["reply"] == diary_interview.SLOT_QUESTIONS["어떻게"]
    assert body["done"] is False
    assert body["slots"]["무엇을"] == "회의"


@pytest.mark.parametrize(
    "response",
    [
        RuntimeError("LLM_API_KEY가 설정되지 않았습니다"),
        '{"slots": {}, "summary": "그 회의는',
        "회의는 어디에서 있었어요?",  # JSON이 아닌 평문
        "[]",
        "",
    ],
)
def test_interview_turn_falls_back_to_fixed_questions(monkeypatch, response):
    _fake_chat(monkeypatch, response)

    first = _post().json()
    second = _post(user_text="어제요.", history=_history_with_follow_ups(1)).json()
    after_wrap_up = _post(user_text="없어요.", history=_history_after_wrap_up()).json()
    last = _post(
        user_text="어제요.", history=_history_with_follow_ups(diary_interview.MAX_FOLLOW_UPS)
    ).json()

    assert first["reply"] == diary_interview.FALLBACK_QUESTIONS[0]
    assert first["done"] is False
    assert second["reply"] == diary_interview.FALLBACK_QUESTIONS[1]
    assert diary_interview.FALLBACK_QUESTIONS[-1] == diary_interview.WRAP_UP
    for body in (after_wrap_up, last):
        assert body["reply"] in diary_interview.CLOSINGS
        assert body | {"reply": None} == {
            "reply": None,
            "done": True,
            "crisis": False,
            "slots": {},
            "missing": [],
            "summary": None,
        }


def test_interview_turn_cleans_slot_values(monkeypatch):
    _fake_chat(
        monkeypatch,
        json.dumps({"slots": {"무엇을": "  회의  ", "언제": "   ", "기분": "속상함"}}, ensure_ascii=False),
        "어디였어요?",
    )

    slots = _post().json()["slots"]

    assert slots["무엇을"] == "회의"
    assert slots["언제"] is None
    assert set(slots) == set(diary_interview.SLOTS)


@pytest.mark.parametrize(
    "summary, expected",
    [
        ("  오늘은 팀 회의에서 의견이 무시당한 하루였어요.  ", "오늘은 팀 회의에서 의견이 무시당한 하루였어요."),
        ("   ", None),
        (None, None),
    ],
)
def test_interview_turn_returns_the_diary_summary(monkeypatch, summary, expected):
    _fake_chat(monkeypatch, _facts(summary=summary, 무엇을="회의"), "어디였어요?")

    assert _post().json()["summary"] == expected


def test_interview_prompt_keeps_the_summary_to_what_the_user_said():
    prompt = diary_interview.EXTRACT_PROMPT
    assert '"summary"' in prompt
    assert "말하지 않은 감정이나 내용은 넣지 않는다" in prompt


def test_interview_turn_stops_on_crisis_without_llm(monkeypatch):
    calls = _fake_chat(monkeypatch, AssertionError("LLM must not be called"))

    body = _post(user_text="요즘은 그냥 죽고 싶다는 생각만 들어요.").json()

    assert body["crisis"] is True
    assert body["done"] is False
    assert "109" in body["reply"]
    assert calls == []


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
