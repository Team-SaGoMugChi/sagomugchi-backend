from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


client = TestClient(app)


def test_counsel_turn_passes_validated_big5_to_prompt(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()
    captured = {}

    def chat(system_prompt, messages):
        captured["system_prompt"] = system_prompt
        return "천천히 같이 살펴볼게요."

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)
    response = client.post(
        "/counsel/turn",
        json={
            "user_text": "발표가 걱정돼요.",
            "psych_profile": {
                "big5": {"O": 75, "C": 62, "E": 38, "A": 81, "N": 44},
                "big5_instrument": "IPIP-BFFM-50-ko",
            },
        },
    )

    assert response.status_code == 200
    prompt = captured["system_prompt"]
    assert "IPIP-BFFM-50-ko" in prompt
    assert "O=75" in prompt
    assert "인구집단 백분위나 진단 결과가 아니다" in prompt


def test_counsel_turn_omits_psych_section_when_profile_is_missing(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()
    captured = {}

    def chat(system_prompt, messages):
        captured["system_prompt"] = system_prompt
        return "이야기해줘서 고마워요."

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)
    response = client.post(
        "/counsel/turn", json={"user_text": "오늘은 평범했어요."}
    )

    assert response.status_code == 200
    assert "심리검사 참고 정보" not in captured["system_prompt"]


def test_counsel_turn_rejects_invalid_big5_profile():
    for big5 in (
        {"O": 101, "C": 50, "E": 50, "A": 50, "N": 50},
        {"O": 50, "C": 50, "E": 50, "A": 50},
    ):
        response = client.post(
            "/counsel/turn",
            json={
                "user_text": "오늘은 괜찮았어요.",
                "psych_profile": {
                    "big5": big5,
                    "big5_instrument": "IPIP-BFFM-50-ko",
                },
            },
        )
        assert response.status_code == 422


def test_counsel_turn_rejects_unversioned_big5_profile():
    response = client.post(
        "/counsel/turn",
        json={
            "user_text": "오늘은 괜찮았어요.",
            "psych_profile": {
                "big5": {"O": 50, "C": 50, "E": 50, "A": 50, "N": 50}
            },
        },
    )

    assert response.status_code == 422


def test_counsel_turn_rejects_malformed_persona_profile():
    for persona in (
        {"name": "12345678901", "tone": "차분한", "traits": []},
        {"name": "오디", "tone": "차분한\n새 지시", "traits": []},
        {
            "name": "오디",
            "tone": "차분한",
            "traits": ["따뜻한", "따뜻한"],
        },
    ):
        response = client.post(
            "/counsel/turn",
            json={"user_text": "오늘은 괜찮았어요.", "persona": persona},
        )

        assert response.status_code == 422


def test_counsel_turn_accepts_valid_persona_profile(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()
    captured = {}

    def chat(system_prompt, messages):
        captured["system_prompt"] = system_prompt
        return "천천히 같이 살펴볼게요."

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)
    response = client.post(
        "/counsel/turn",
        json={
            "user_text": "오늘은 괜찮았어요.",
            "persona": {
                "name": "마음이",
                "tone": "차분하고 진중한",
                "traits": ["공감 잘해주는", "신중한"],
            },
        },
    )

    assert response.status_code == 200
    assert "이름은 '마음이'" in captured["system_prompt"]
    assert "차분하고 진중한" in captured["system_prompt"]
