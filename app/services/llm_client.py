"""OpenAI 호출을 한 곳으로 모은다.

키와 모델은 .env에서 읽는다(app/core/config.py). 키가 없으면 RuntimeError를
던지고, 호출하는 쪽이 고정 응답으로 폴백한다.
"""

import re
from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings

# 추론형 모델(gpt-5 이후, o 시리즈)은 max_tokens·temperature를 받지 않는다(넣으면 400).
_REASONING_MODEL = re.compile(r"^(gpt-([5-9]|\d{2,})|o\d)")

# reasoning_effort가 none이 아니면 답 앞에 추론 토큰을 쓰므로, 답이 잘리지 않게 그만큼 더 준다.
_REASONING_BUDGET = 4000


def is_reasoning_model(model: str) -> bool:
    return bool(_REASONING_MODEL.match(model))


def _sampling(model: str, temperature: float, max_tokens: int) -> dict:
    """모델 종류에 맞는 생성 파라미터. 추론형은 temperature를 기본값(1)으로만 쓴다."""
    if not is_reasoning_model(model):
        return {"temperature": temperature, "max_tokens": max_tokens}
    effort = get_settings().llm_reasoning_effort
    budget = max_tokens if effort == "none" else max_tokens + _REASONING_BUDGET
    return {"max_completion_tokens": budget, "reasoning_effort": effort}


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
    json_mode: bool = False,
    model: str | None = None,
    timeout: float | None = None,
) -> str:
    """시스템 프롬프트 + 대화 기록 → 답변 한 턴.

    [json_mode] True면 모델이 JSON 객체만 출력하도록 강제한다(OpenAI JSON mode).
                시스템 프롬프트에 'JSON'이라는 말이 들어 있어야 한다.
    [model]     비우면 .env의 LLM_MODEL. 위기 판정처럼 다른 모델을 쓸 때만 넘긴다.
    [timeout]   초 단위 요청 제한. 비우면 OpenAI 기본값.
    [temperature] 추론형 모델(gpt-6-luna 등)에는 보내지 않는다.
    """
    model = model or get_settings().llm_model
    extra: dict = {"response_format": {"type": "json_object"}} if json_mode else {}
    if timeout is not None:
        extra["timeout"] = timeout
    response = _client().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        **_sampling(model, temperature, max_tokens),
        **extra,
    )
    return (response.choices[0].message.content or "").strip()