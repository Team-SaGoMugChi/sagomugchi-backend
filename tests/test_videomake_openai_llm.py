"""스토리보드 LLM의 OpenAI(GPT) 구현. 가짜 클라이언트로 돌려 API 비용 0."""

import asyncio
from types import SimpleNamespace

import pytest

from app.videomake.config import Settings
from app.videomake.errors import ConfigError, ProviderError
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.gemini_llm import GeminiLLMProvider
from app.videomake.providers.openai_llm import OpenAILLMProvider
from app.videomake.providers.registry import build_fake_providers, build_llm
from app.videomake.stages.storyboard import _StoryboardDraft


def _settings(**kwargs) -> Settings:
    # 로컬 .env(예: VIDEOMAKE_LLM_PROVIDER=openai)에 결과가 흔들리지 않게 한다.
    return Settings(_env_file=None, **kwargs)


class _Completions:
    def __init__(self, *, parsed=None, refusal=None, error=None):
        self.parsed, self.refusal, self.error = parsed, refusal, error
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        message = SimpleNamespace(
            parsed=self.parsed, refusal=self.refusal, content='{"ok": true}'
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=450),
        )


def _client(completions: _Completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _draft(n_cuts: int = 2) -> _StoryboardDraft:
    return _StoryboardDraft.model_validate(fake.demo_storyboard_payload(n_cuts))


def test_returns_parsed_schema_and_usage():
    completions = _Completions(parsed=_draft())
    llm = OpenAILLMProvider(_client(completions), "gpt-4o-mini")

    result, meta = asyncio.run(
        llm.complete_json(system="시스템", user="일기", schema=_StoryboardDraft)
    )

    assert isinstance(result, _StoryboardDraft)
    call = completions.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["response_format"] is _StoryboardDraft
    assert call["messages"] == [
        {"role": "system", "content": "시스템"},
        {"role": "user", "content": "일기"},
    ]
    assert (meta.input_tokens, meta.output_tokens) == (120, 450)


def test_refusal_is_provider_error():
    llm = OpenAILLMProvider(_client(_Completions(refusal="거부")), "m")
    with pytest.raises(ProviderError, match="거부"):
        asyncio.run(llm.complete_json(system="s", user="u", schema=_StoryboardDraft))


def test_api_failure_is_provider_error():
    llm = OpenAILLMProvider(_client(_Completions(error=RuntimeError("boom"))), "m")
    with pytest.raises(ProviderError, match="boom"):
        asyncio.run(llm.complete_json(system="s", user="u", schema=_StoryboardDraft))


def test_default_provider_is_openai(monkeypatch):
    """팀 표준은 GPT다. 설정 줄이 없어도 공용 키로 GPT가 시나리오를 짠다."""
    monkeypatch.delenv("VIDEOMAKE_LLM_PROVIDER", raising=False)
    llm = build_llm(_settings(LLM_API_KEY="sk-test"), client=None)
    assert isinstance(llm, OpenAILLMProvider)


def test_gemini_is_still_selectable():
    assert isinstance(build_llm(_settings(llm_provider="gemini"), client=None), GeminiLLMProvider)


def test_openai_provider_uses_shared_key():
    settings = _settings(llm_provider="openai", LLM_API_KEY="sk-test", openai_model="gpt-x")
    llm = build_llm(settings, client=None)
    assert isinstance(llm, OpenAILLMProvider)


def test_openai_provider_without_key_is_config_error():
    with pytest.raises(ConfigError, match="LLM_API_KEY"):
        build_llm(_settings(llm_provider="openai"), client=None)


def test_gpt_storyboard_passes_guardrails(tmp_path):
    """GPT가 준 스토리보드도 Gemini와 똑같이 가드레일 검사를 거쳐 저장된다."""
    settings = _settings(jobs_dir=tmp_path / "jobs", n_cuts=2, cut_duration_seconds=4)
    providers = build_fake_providers(settings)
    completions = _Completions(parsed=_draft(2))
    pipe = Pipeline(
        providers=providers.__class__(
            **{**providers.__dict__, "llm": OpenAILLMProvider(_client(completions), "m")}
        ),
        job=JobStore(settings.jobs_dir, "gpt-job"),
        settings=settings,
    )

    sb = asyncio.run(pipe.plan(DiaryInput(text="오늘 회의에서 있었던 일")))

    assert len(sb.cuts) == 2
    assert pipe.job.storyboard_path.exists()
    assert "오늘 회의에서 있었던 일" in completions.calls[0]["messages"][1]["content"]


def test_reasoning_models_get_no_temperature():
    """gpt-5 계열은 temperature를 받지 않는다(넣으면 400)."""
    completions = _Completions(parsed=_draft())
    asyncio.run(
        OpenAILLMProvider(_client(completions), "gpt-5.5").complete_json(
            system="s", user="u", schema=_StoryboardDraft
        )
    )
    asyncio.run(
        OpenAILLMProvider(_client(completions), "gpt-4o").complete_json(
            system="s", user="u", schema=_StoryboardDraft
        )
    )
    assert "temperature" not in completions.calls[0]
    assert completions.calls[1]["temperature"] == 0.9


def test_default_openai_model_is_gpt_5_5(monkeypatch):
    monkeypatch.delenv("VIDEOMAKE_OPENAI_MODEL", raising=False)
    assert _settings().openai_model == "gpt-5.5"
