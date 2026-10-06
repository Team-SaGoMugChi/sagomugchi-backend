"""일기 전달 JSON(`oddo.diary_emotion.v1`) → 스토리보드 프롬프트 재료.

전달 JSON은 일기 기록 파트가 만든다(app/services/diary_handoff.py). 스토리보드에는
장면 구성에 쓰이는 것만 고른다. 문장별 감정(sentences)·필드 설명(설명)·원문은 넣지 않는다 —
장면과 전환점에 이미 요약돼 있고, 길면 LLM이 연출 규칙을 덜 지킨다.

앱이 만든 JSON이라 형식을 믿지 않는다. 스키마가 다르거나 칸이 깨져 있으면 그 칸만 버리고,
쓸 게 없으면 None을 돌려 예전처럼 일기 글과 감정 결과만으로 만든다.
"""

from __future__ import annotations

from typing import Any

SCHEMA = "oddo.diary_emotion.v1"


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _strings(value: Any) -> list[str]:
    return [s for v in value if (s := _text(v))] if isinstance(value, list) else []


def _dicts(value: Any) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def diary_text(handoff: dict[str, Any] | None) -> str | None:
    """정제·확인된 일기. 대화 원문보다 사건 순서가 정리돼 있어 시나리오 입력으로 낫다."""
    if not handoff or handoff.get("schema") != SCHEMA:
        return None
    diary = handoff.get("diary")
    return _text(diary.get("diary_text")) if isinstance(diary, dict) else None


def storyboard_context(handoff: dict[str, Any] | None) -> dict[str, Any] | None:
    if not handoff or handoff.get("schema") != SCHEMA:
        return None
    diary = handoff.get("diary") if isinstance(handoff.get("diary"), dict) else {}
    overall = (
        handoff.get("emotion_overall") if isinstance(handoff.get("emotion_overall"), dict) else {}
    )
    slots = diary.get("slots") if isinstance(diary.get("slots"), dict) else {}
    context = {
        "summary": _text(diary.get("summary")),
        "slots": {k: v for k, raw in slots.items() if (v := _text(raw))},
        "arc": _text(overall.get("arc")),
        "signals": _strings(overall.get("signals")),
        "incongruent": overall.get("incongruent") is True,
        "scenes": [
            {
                "order": s.get("order"),
                "tone": _text(s.get("tone")) or "중립",
                "emotions": _strings(s.get("emotions")),
                "intensity": s.get("intensity") if isinstance(s.get("intensity"), int) else None,
                "text": text,
            }
            for s in _dicts(handoff.get("scenes"))
            if (text := _text(s.get("text")))
        ],
        "turning_points": [
            {"from": _text(p.get("from")), "to": _text(p.get("to")), "sentence": sentence}
            for p in _dicts(handoff.get("turning_points"))
            if (sentence := _text(p.get("sentence")))
        ],
    }
    has_material = any(
        context[k] for k in ("summary", "slots", "arc", "signals", "scenes", "turning_points")
    )
    return context if has_material or context["incongruent"] else None
