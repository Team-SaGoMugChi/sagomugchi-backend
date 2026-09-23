"""OpenAI 호출을 한 곳으로 모은다.

키와 모델은 .env에서 읽는다(app/core/config.py). 키가 없으면 RuntimeError를
던지고, 호출하는 쪽이 고정 응답으로 폴백한다.
"""

from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings


@lru_cache
def _client() -> OpenAI:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY가 설정되지 않았습니다 (.env 참고)")
    return OpenAI(api_key=settings.llm_api_key)


def chat(
    system_prompt: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 300,
) -> str:
    """시스템 프롬프트 + 대화 기록 → 답변 한 턴."""
    response = _client().chat.completions.create(
        model=get_settings().llm_model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system_prompt}, *messages],
    )
    return (response.choices[0].message.content or "").strip()