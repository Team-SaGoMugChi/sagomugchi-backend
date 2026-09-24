"""상담 리포트 생성 — 대화를 돌아보는 글로 정리한다.

Step 4 상담이 끝나면 46번 화면에 보여줄 리포트를 만든다. 상담 중의 말투 규칙을
그대로 따르되, 대화가 아니라 "오늘 이야기를 정리한 글"이라는 점이 다르다.

원칙 (counsel_prompt.py와 같은 근거)
- 진단하지 않는다. 대화에 나온 말 안에서만 근거를 찾는다.
- 사용자가 말하지 않은 사실을 지어내지 않는다.
- "괜찮아질 거예요" 같은 근거 없는 위로로 닫지 않는다.
- 감정 점수를 숫자로 읽어주지 않는다. 점수는 앱이 그래프로 따로 보여준다.

LLM이 JSON을 주지 않거나 호출이 실패해도 화면이 비지 않도록, 항상 폴백
리포트를 돌려준다.
"""

from __future__ import annotations

import json
import re

from app.services import llm_client

_REPORT_SYSTEM = """너는 감정 일기 앱의 상담 리포트를 쓰는 작성자다.
방금 끝난 상담 대화를 읽고, 사용자가 나중에 다시 읽어볼 글로 정리한다.

[쓰는 방식]
- 편한 존댓말. 담백하게 쓴다.
- 호칭을 쓰지 않는다. '~님', '당신', '사용자'라고 부르지 않는다.
- 이모지와 과장된 표현을 쓰지 않는다.
- 대화에 나온 말 안에서만 근거를 찾는다. 없는 사실을 지어내지 않는다.
- 감정 점수를 숫자로 적지 않는다.

[하지 않을 것]
- 진단명이나 약을 언급하지 않는다.
- "괜찮아질 거예요", "별일 아니에요" 같은 근거 없는 위로를 쓰지 않는다.
- 감정을 고쳐야 할 문제로 다루지 않는다.
- 조언을 길게 늘어놓지 않는다.

[출력 형식]
JSON만 출력한다. 설명을 덧붙이지 않는다.
{
  "headline": "오늘을 한 문장으로. 20자 안팎.",
  "summary": "무슨 일이 있었고 어떻게 느꼈는지 2~3문장.",
  "moments": ["대화 중 스스로 알아차린 점 1~3개. 각 한 문장."],
  "reframe": "같은 일을 달리 볼 수 있는 관점 한 문장. 단정하지 말고 제안하듯.",
  "suggestion": "아주 작은 행동 하나. 한 문장. 없으면 빈 문자열.",
  "closing": "마무리 한 문장. 답을 내지 않아도 된다는 쪽이어도 좋다."
}"""

_FALLBACK = {
    "headline": "오늘의 이야기",
    "summary": "오늘 나눈 이야기를 정리하지 못했어요. 대화 내용은 그대로 남아 있어요.",
    "moments": [],
    "reframe": "",
    "suggestion": "",
    "closing": "다음에 다시 이야기해도 괜찮아요.",
}

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _describe_emotions(emotions: dict[str, float] | None) -> str:
    """상위 감정만 강도 표현으로. 숫자를 프롬프트에 넣지 않는다."""
    if not emotions:
        return ""
    top = sorted(emotions.items(), key=lambda kv: kv[1], reverse=True)[:3]
    parts = []
    for name, score in top:
        level = "강하게" if score >= 70 else ("어느 정도" if score >= 40 else "약하게")
        parts.append(f"{name}({level})")
    return ", ".join(parts)


def _build_user_prompt(
    messages: list[dict],
    emotions: dict[str, float] | None,
    diary_summary: str | None,
) -> str:
    lines: list[str] = []
    if diary_summary:
        lines.append(f"[오늘 일기 요약] {diary_summary}")
    described = _describe_emotions(emotions)
    if described:
        lines.append(f"[분석된 감정] {described} (참고용이고 틀릴 수 있다)")

    lines.append("\n[상담 대화]")
    for m in messages:
        speaker = "상담봇" if m["role"] == "assistant" else "사용자"
        lines.append(f"{speaker}: {m['content']}")

    lines.append("\n위 대화를 읽고 지정한 JSON 형식으로만 답한다.")
    return "\n".join(lines)


def _parse(raw: str) -> dict:
    """LLM 응답에서 JSON을 꺼낸다. 코드 펜스가 붙어 오는 경우가 있다."""
    text = _FENCE.sub("", (raw or "").strip())
    try:
        data = json.loads(text)
    except ValueError:
        return dict(_FALLBACK)
    if not isinstance(data, dict):
        return dict(_FALLBACK)

    moments = data.get("moments") or []
    if not isinstance(moments, list):
        moments = []

    return {
        "headline": str(data.get("headline") or _FALLBACK["headline"]).strip(),
        "summary": str(data.get("summary") or _FALLBACK["summary"]).strip(),
        "moments": [str(m).strip() for m in moments if str(m).strip()][:3],
        "reframe": str(data.get("reframe") or "").strip(),
        "suggestion": str(data.get("suggestion") or "").strip(),
        "closing": str(data.get("closing") or _FALLBACK["closing"]).strip(),
    }


def build(
    messages: list[dict],
    emotions: dict[str, float] | None = None,
    diary_summary: str | None = None,
) -> dict:
    """상담 대화로 리포트를 만든다. 실패해도 폴백 리포트를 돌려준다.

    [messages]      {"role": "user"|"assistant", "content": str} 목록.
    [emotions]      Step2 분석 점수. 강도 표현으로만 전달된다.
    [diary_summary] 오늘 일기 요약.
    """
    # 대화가 거의 없으면 LLM을 부르지 않는다 — 지어낸 리포트가 나오기 쉽다.
    user_turns = sum(1 for m in messages if m["role"] == "user")
    if user_turns < 2:
        short = dict(_FALLBACK)
        short["summary"] = "오늘은 이야기를 짧게 나눴어요. 여기까지도 충분해요."
        return short

    try:
        raw = llm_client.chat(
            _REPORT_SYSTEM,
            [{"role": "user", "content": _build_user_prompt(messages, emotions, diary_summary)}],
        )
    except Exception:
        # 키 미설정·네트워크 오류 등 — 화면이 비지 않도록 폴백.
        return dict(_FALLBACK)

    return _parse(raw)