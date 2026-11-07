"""공용 LLM 호출 — 모델 종류에 맞는 파라미터를 보내는지. 가짜 클라이언트로 돌려 API 비용 0."""

from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.services import llm_client


class _Completions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=" 안녕 ")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def completions(monkeypatch):
    fake = _Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    monkeypatch.setattr(llm_client, "_client", lambda: client)
    return fake


def _use(monkeypatch, model: str, effort: str | None = None):
    monkeypatch.setenv("LLM_MODEL", model)
    if effort:
        monkeypatch.setenv("LLM_REASONING_EFFORT", effort)
    else:
        monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "model, expected",
    [
        ("gpt-6-luna", True),
        ("gpt-5.5", True),
        ("o3", True),
        ("gpt-4o", False),
        ("gpt-4o-mini", False),
        ("ft:gpt-4o-2024-08-06:oddo::abc", False),
    ],
)
def test_reasoning_model_detection(model, expected):
    assert llm_client.is_reasoning_model(model) is expected


def test_reasoning_model_gets_completion_tokens_and_no_temperature(monkeypatch, completions):
    """gpt-6-luna는 max_tokens·temperature를 받지 않는다(넣으면 400)."""
    _use(monkeypatch, "gpt-6-luna")
    reply = llm_client.chat("s", [{"role": "user", "content": "u"}], temperature=0, max_tokens=120)

    call = completions.calls[0]
    assert reply == "안녕"
    assert call["model"] == "gpt-6-luna"
    assert call["max_completion_tokens"] == 120
    assert call["reasoning_effort"] == "none"
    assert "max_tokens" not in call and "temperature" not in call


def test_reasoning_effort_above_none_adds_budget(monkeypatch, completions):
    """추론 토큰이 답 몫을 먹지 않게 한도를 늘린다."""
    _use(monkeypatch, "gpt-6-luna", effort="low")
    llm_client.chat("s", [], max_tokens=120)

    call = completions.calls[0]
    assert call["reasoning_effort"] == "low"
    assert call["max_completion_tokens"] == 120 + llm_client._REASONING_BUDGET


def test_non_reasoning_model_keeps_old_parameters(monkeypatch, completions):
    """.env가 아직 gpt-4o-mini인 팀원도 그대로 돌아간다."""
    _use(monkeypatch, "gpt-4o-mini")
    llm_client.chat("s", [], temperature=0, max_tokens=500, json_mode=True)

    call = completions.calls[0]
    assert call["temperature"] == 0
    assert call["max_tokens"] == 500
    assert call["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in call


def test_model_argument_overrides_setting(monkeypatch, completions):
    """위기 판정처럼 model을 넘기면 그 모델 기준으로 파라미터를 고른다."""
    _use(monkeypatch, "gpt-4o-mini")
    llm_client.chat("s", [], model="gpt-6-luna", max_tokens=60)

    call = completions.calls[0]
    assert call["model"] == "gpt-6-luna"
    assert "temperature" not in call


def test_default_model_is_gpt_6_luna(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("COUNSEL_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    settings = type(get_settings())(_env_file=None)
    assert settings.llm_model == "gpt-6-luna"
    assert settings.counsel_judge_model == "gpt-6-luna"
    assert settings.llm_reasoning_effort == "none"
