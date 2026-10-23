import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services import counsel_cbt


client = TestClient(app)


def _llm(reply, advance=False, extracted=None, captured=None):
    def chat(system_prompt, messages, **kwargs):
        if captured is not None:
            captured["system_prompt"] = system_prompt
            captured["kwargs"] = kwargs
        return json.dumps(
            {"reply": reply, "advance": advance, "extracted": extracted or {}},
            ensure_ascii=False,
        )

    return chat


def _no_dummy(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()


# --- 단계 계산 --------------------------------------------------------------


def test_resolve_stage_skips_mission_check_without_last_mission():
    assert counsel_cbt.resolve_stage(0, None) == 1
    assert counsel_cbt.resolve_stage(0, "  ") == 1
    assert counsel_cbt.resolve_stage(0, "10분 산책") == 0
    assert counsel_cbt.resolve_stage(3, None) == 3


def test_next_state_advances_or_stays():
    assert counsel_cbt.next_state(2, 0, advance=True) == (3, 0, False)
    assert counsel_cbt.next_state(2, 0, advance=False) == (2, 1, False)


def test_next_state_forces_advance_after_max_turns():
    last = counsel_cbt.MAX_STAGE_TURNS - 1
    assert counsel_cbt.next_state(2, last, advance=False) == (3, 0, False)


def test_next_state_ends_session_after_last_stage():
    assert counsel_cbt.next_state(5, 0, advance=True) == (5, 0, True)


def test_parse_output_falls_back_to_raw_text_on_broken_json():
    out = counsel_cbt.parse_output("그랬군요.")
    assert out.reply == "그랬군요."
    assert out.advance is False
    assert out.extracted == {}


def test_parse_output_ignores_non_bool_advance():
    out = counsel_cbt.parse_output('{"reply": "네.", "advance": "true", "extracted": []}')
    assert out.advance is False
    assert out.extracted == {}


# --- /counsel/turn CBT 모드 ---------------------------------------------------


def test_cbt_turn_advances_and_returns_extracted(monkeypatch):
    _no_dummy(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        "app.api.routes.counsel.llm_client.chat",
        _llm(
            "불안이 7 정도였군요. 그때 무슨 일이 있었나요?",
            advance=True,
            extracted={"emotionLabel": "불안", "intensity": 7},
            captured=captured,
        ),
    )

    response = client.post(
        "/counsel/turn",
        json={"user_text": "불안했어요. 7 정도요.", "cbt": {"stage": 1, "style": "analysis"}},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["cbt"] == {
        "stage": 2,
        "stage_turn": 0,
        "extracted": {"emotionLabel": "불안", "intensity": 7},
        "done": False,
    }
    assert "[현재 CBT 단계: 1. 감정 확인]" in captured["system_prompt"]
    assert "분석형" in captured["system_prompt"]
    assert "JSON" in captured["system_prompt"]
    assert captured["kwargs"]["json_mode"] is True


def test_cbt_turn_skips_stage_zero_without_mission(monkeypatch):
    _no_dummy(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        "app.api.routes.counsel.llm_client.chat",
        _llm("오늘 기분은 어떤 단어에 가까울까요?", captured=captured),
    )

    response = client.post(
        "/counsel/turn", json={"user_text": "안녕", "cbt": {"stage": 0}}
    )

    assert response.json()["cbt"]["stage"] == 1
    assert response.json()["cbt"]["stage_turn"] == 1
    assert "감정 확인" in captured["system_prompt"]


def test_cbt_turn_mission_check_uses_last_mission(monkeypatch):
    _no_dummy(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        "app.api.routes.counsel.llm_client.chat",
        _llm("산책해보셨다니 반가워요. 해보니 어땠나요?", captured=captured),
    )

    client.post(
        "/counsel/turn",
        json={
            "user_text": "산책 했어요",
            "cbt": {"stage": 0, "last_mission": "점심 먹고 10분 산책"},
        },
    )

    assert "점심 먹고 10분 산책" in captured["system_prompt"]


def test_cbt_turn_last_stage_marks_done(monkeypatch):
    _no_dummy(monkeypatch)
    monkeypatch.setattr(
        "app.api.routes.counsel.llm_client.chat",
        _llm(
            "내일 10분 산책으로 정해요. 오늘 이야기 나눠줘서 고마워요.",
            advance=True,
            extracted={"mission": "점심 먹고 10분 산책"},
        ),
    )

    response = client.post(
        "/counsel/turn", json={"user_text": "산책할게요", "cbt": {"stage": 5}}
    )

    state = response.json()["cbt"]
    assert state["done"] is True
    assert state["extracted"] == {"mission": "점심 먹고 10분 산책"}


def test_cbt_turn_crisis_keeps_stage_without_llm(monkeypatch):
    def chat(*args, **kwargs):
        raise AssertionError("CRISIS에서는 LLM을 부르지 않는다")

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)

    response = client.post(
        "/counsel/turn",
        json={"user_text": "죽고 싶어", "cbt": {"stage": 3, "stage_turn": 1}},
    )

    body = response.json()
    assert body["crisis"] is True
    assert body["cbt"] == {"stage": 3, "stage_turn": 1, "extracted": {}, "done": False}


def test_cbt_turn_llm_error_keeps_stage(monkeypatch):
    _no_dummy(monkeypatch)

    def chat(*args, **kwargs):
        raise RuntimeError("no key")

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)

    response = client.post(
        "/counsel/turn", json={"user_text": "음", "cbt": {"stage": 2}}
    )

    assert response.json()["cbt"] == {
        "stage": 2,
        "stage_turn": 0,
        "extracted": {},
        "done": False,
    }


def test_cbt_turn_unsafe_reply_does_not_advance(monkeypatch):
    _no_dummy(monkeypatch)
    monkeypatch.setattr(
        "app.api.routes.counsel.llm_client.chat",
        _llm("우울증 같아요.", advance=True, extracted={"insight": "x"}),
    )

    response = client.post(
        "/counsel/turn", json={"user_text": "그냥 힘들어요", "cbt": {"stage": 3}}
    )

    state = response.json()["cbt"]
    assert state["stage"] == 3
    assert state["extracted"] == {}