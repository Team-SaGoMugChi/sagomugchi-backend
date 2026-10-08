"""상담 리포트 생성 — 대화를 돌아보는 글로 정리한다.

Step 4 상담이 끝나면 46번 화면에 보여줄 리포트를 만든다. 상담 중의 말투 규칙을
그대로 따르되, 대화가 아니라 "오늘 이야기를 정리한 글"이라는 점이 다르다.

원칙 (counsel_prompt.py와 같은 근거)
- 진단하지 않는다. 대화에 나온 말 안에서만 근거를 찾는다.
- 사용자가 말하지 않은 사실을 지어내지 않는다.
- "괜찮아질 거예요" 같은 근거 없는 위로로 닫지 않는다.
- 감정 점수를 숫자로 읽어주지 않는다. 점수는 앱이 그래프로 따로 보여준다.

할루시네이션 방지
1. 프롬프트: 사용자의 말과 일기 대화 칸(slots)만 근거로 쓰라고 지시한다.
2. 생성: JSON mode + 낮은 temperature(0.3)로 형식 깨짐과 창작을 줄인다.
3. 검증: `moments`·`reframe`이 사용자가 실제로 한 말과 겹치는지 글자 단위로
   확인하고, 근거가 없는 문장은 버린다(`_ground`). LLM이 그럴듯하게 지어낸
   "알아차린 점"이 리포트에 남지 않게 하는 마지막 거름망이다.

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
- 감정 점수를 숫자로 적지 않는다.

[근거 — 가장 중요하다]
- 근거로 쓸 수 있는 것은 [상담 대화]에서 사용자가 한 말과 [오늘 일기 사실]뿐이다.
- 상담봇이 한 말은 사용자의 생각이 아니다. 상담봇이 제안했지만 사용자가
  동의하지 않은 내용을 사용자가 알아차린 것처럼 쓰지 않는다.
- 사람·장소·사건·감정을 새로 만들지 않는다. 대화에 없는 내용은 쓰지 않는다.
- moments는 사용자가 대화 중 직접 말한 깨달음·변화만 쓴다. 사용자의 표현을
  최대한 살린다. 없으면 빈 배열로 둔다.

[하지 않을 것]
- 진단명이나 약을 언급하지 않는다.
- "괜찮아질 거예요", "별일 아니에요" 같은 근거 없는 위로를 쓰지 않는다.
- 감정을 고쳐야 할 문제로 다루지 않는다.
- 조언을 길게 늘어놓지 않는다.

[출력 형식]
JSON 객체만 출력한다. 설명을 덧붙이지 않는다.
{
  "headline": "오늘을 한 문장으로. 20자 안팎.",
  "summary": "무슨 일이 있었고 어떻게 느꼈는지 2~3문장.",
  "moments": ["대화 중 사용자가 스스로 알아차린 점 0~3개. 각 한 문장."],
  "reframe": "같은 일을 달리 볼 수 있는 관점 한 문장. 단정하지 말고 제안하듯. 근거가 없으면 빈 문자열.",
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

# 리포트 생성은 형식이 중요하고 창작이 필요 없다.
_TEMPERATURE = 0.3
# 한국어 JSON 6개 필드 — 300토큰이면 잘려서 파싱에 실패할 수 있다.
_MAX_TOKENS = 700

# 근거 확인에서 빼는 글자쌍 — 어미·조사·리포트에 흔한 말이라 겹쳐도 근거가 아니다.
_STOP_BIGRAMS = frozenset(
    {
        "어요", "아요", "해요", "했어", "했다", "있었", "었어", "었다", "는데",
        "지만", "에서", "으로", "하고", "니다", "습니", "것을", "것이", "하는",
        "했던", "있는", "없는", "이야", "야기", "오늘", "조금", "마음", "생각",
        "기분", "느낌", "느꼈", "스스", "스로", "자신", "알아", "아차", "차렸",
        "렸어", "보면", "같아", "같은", "그때", "때문", "어서", "아서", "해서",
    }
)
# moments 한 문장이 사용자 말과 최소 몇 개의 글자쌍을 공유해야 하는지.
_MOMENT_MIN_OVERLAP = 2
_REFRAME_MIN_OVERLAP = 1


def _bigrams(text: str) -> set[str]:
    """한글·영문·숫자만 남기고 붙여 쓴 뒤 두 글자씩 자른다."""
    compact = "".join(re.findall(r"[가-힣A-Za-z0-9]+", text))
    return {compact[i : i + 2] for i in range(len(compact) - 1)} - _STOP_BIGRAMS


def _is_grounded(sentence: str, source: set[str], minimum: int) -> bool:
    return len(_bigrams(sentence) & source) >= minimum


def _ground(report: dict, user_texts: list[str]) -> dict:
    """사용자 말과 겹치지 않는 moments·reframe을 버린다."""
    source: set[str] = set()
    for text in user_texts:
        source |= _bigrams(text)

    report["moments"] = [
        m for m in report["moments"] if _is_grounded(m, source, _MOMENT_MIN_OVERLAP)
    ]
    if report["reframe"] and not _is_grounded(
        report["reframe"], source, _REFRAME_MIN_OVERLAP
    ):
        report["reframe"] = ""
    return report


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
    slots: dict[str, str] | None,
) -> str:
    lines: list[str] = []
    if slots:
        lines.append("[오늘 일기 사실 — 사용자가 일기 대화에서 직접 말한 내용]")
        lines += [f"- {key}: {value}" for key, value in slots.items() if value]
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
    slots: dict[str, str] | None = None,
) -> dict:
    """상담 대화로 리포트를 만든다. 실패해도 폴백 리포트를 돌려준다.

    [messages]      {"role": "user"|"assistant", "content": str} 목록.
    [emotions]      Step2 분석 점수. 강도 표현으로만 전달된다.
    [diary_summary] 오늘 일기 요약.
    [slots]         일기 대화에서 사용자가 말한 칸. 근거 확인에도 쓴다.
    """
    # 대화가 거의 없으면 LLM을 부르지 않는다 — 지어낸 리포트가 나오기 쉽다.
    user_texts = [m["content"] for m in messages if m["role"] == "user"]
    if len(user_texts) < 2:
        short = dict(_FALLBACK)
        short["summary"] = "오늘은 이야기를 짧게 나눴어요. 여기까지도 충분해요."
        return short

    try:
        raw = llm_client.chat(
            _REPORT_SYSTEM,
            [
                {
                    "role": "user",
                    "content": _build_user_prompt(
                        messages, emotions, diary_summary, slots
                    ),
                }
            ],
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
            json_mode=True,
        )
    except Exception:
        # 키 미설정·네트워크 오류 등 — 화면이 비지 않도록 폴백.
        return dict(_FALLBACK)

    report = _parse(raw)
    # 일기 칸도 사용자가 직접 한 말이므로 근거로 인정한다.
    sources = user_texts + [v for v in (slots or {}).values() if v]
    return _ground(report, sources)