from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


client = TestClient(app)


def test_counsel_turn_uses_real_analysis_context(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()
    captured = {}

    def chat(system_prompt, messages):
        captured["system_prompt"] = system_prompt
        captured["messages"] = messages
        return "천천히 같이 살펴볼게요."

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)

    response = client.post(
        "/counsel/turn",
        json={
            "user_text": "발표가 걱정돼요.",
            "history": [{"speaker": "oddo", "text": "무슨 일이 있었나요?"}],
            "emotions": {"불안": 72.0},
            "signals": ["말 속도가 평소보다 빠름"],
            "diary_summary": "내일 발표가 있어서 긴장된다고 적음",
            "incongruent": True,
            "persona": {
                "name": "오디",
                "tone": "따뜻한",
                "traits": ["공감"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "천천히 같이 살펴볼게요.",
        "crisis": False,
        "risk_axis": None,
        "used_dummy_context": False,
    }
    prompt = captured["system_prompt"]
    assert "내일 발표가 있어서 긴장된다고 적음" in prompt
    assert "불안" in prompt
    assert "말 속도가 평소보다 빠름" in prompt
    assert "말과 신호의 차이" in prompt
    assert "오디" in prompt
    assert captured["messages"] == [
        {"role": "assistant", "content": "무슨 일이 있었나요?"},
        {"role": "user", "content": "발표가 걱정돼요."},
    ]


def test_counsel_turn_does_not_invent_missing_context(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()
    captured = {}

    def chat(system_prompt, messages):
        captured["system_prompt"] = system_prompt
        return "이야기해줘서 고마워요."

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)

    response = client.post(
        "/counsel/turn",
        json={"user_text": "오늘은 그냥 평범했어요."},
    )

    assert response.status_code == 200
    assert response.json()["used_dummy_context"] is False
    prompt = captured["system_prompt"]
    assert "자기 비난" not in prompt
    assert "말 속도가 평소보다 느림" not in prompt


def test_counsel_turn_crisis_returns_axis_reply_without_llm(monkeypatch):
    def chat(system_prompt, messages):
        raise AssertionError("CRISIS에서는 LLM을 부르지 않는다")

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)

    response = client.post("/counsel/turn", json={"user_text": "지금 아빠가 때리고 있어"})

    body = response.json()
    assert body["crisis"] is True
    assert body["risk_axis"] == "danger"
    assert "112" in body["reply"]


def test_counsel_turn_caution_adds_axis_guide(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()
    captured = {}

    def chat(system_prompt, messages):
        captured["system_prompt"] = system_prompt
        return "그렇게 말해줘서 고마워요."

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)

    response = client.post("/counsel/turn", json={"user_text": "나한테는 너밖에 없어"})

    body = response.json()
    assert body["crisis"] is False
    assert body["risk_axis"] == "dependence"
    assert "AI인 오또에게만 의지" in captured["system_prompt"]