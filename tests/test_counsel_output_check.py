"""응답 검증 레이어 — 규칙 위반 검사, 재생성, 자동 수정, 안전 문장."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.counsel_output_check import (
    SAFE_REPLY,
    check_reply,
    feedback_for,
    repair,
    verify,
)

client = TestClient(app)

GOOD = "의견이 그냥 넘어가서 서운하셨겠어요. 그때 어떤 생각이 스쳤어요?"


def _codes(reply, **kwargs):
    return [v.code for v in check_reply(reply, **kwargs)]


# ── 검사 ─────────────────────────────────────────────────────────────

def test_good_reply_passes():
    assert check_reply(GOOD) == []


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        ("우울증 증상일 수 있어요. 요즘 잠은 어때요?", "diagnosis"),
        ("항우울제 상담을 받아보는 것도 방법이에요.", "medication"),
        ("뛰어내리고 싶은 마음이 드셨군요.", "method"),
        ("지난번에도 비슷한 일로 힘들어하셨죠. 오늘은 어때요?", "fake_memory"),
        ("어떤 기분이었어요? 누구와 있었어요?", "multi_question"),
        ("괜찮아질 거예요. 오늘은 푹 쉬어요.", "false_comfort"),
        ("서운하셨겠어요 😢 어떤 생각이 들었어요?", "emoji"),
        ("가. 나. 다. 라. 마.", "too_long"),
    ],
)
def test_detects_each_rule(reply, code):
    assert code in _codes(reply)


def test_allows_echoing_words_the_user_said_first():
    reply = "우울증일까 봐 걱정되셨군요. 어떤 때 그런 생각이 들었어요?"
    assert "diagnosis" not in _codes(reply, user_texts=["혹시 나 우울증일까 봐 걱정돼"])


def test_past_session_mention_is_ok_when_themes_exist():
    reply = "지난 상담에서도 스스로를 탓하는 이야기가 있었어요. 오늘도 그런가요?"
    assert "fake_memory" not in _codes(reply, has_recent_themes=True)


def test_crisis_hotline_is_not_a_method():
    reply = "힘들면 자살예방상담전화 109에서도 이야기를 들어줘요."
    assert "method" not in _codes(reply)


def test_feedback_lists_broken_rules():
    text = feedback_for(check_reply("우울증 같아요? 언제부터요?"))
    assert "진단명을 말하지 않는다" in text
    assert "질문을 하나만 한다" in text


# ── 자동 수정 ────────────────────────────────────────────────────────

def test_repair_keeps_only_first_question():
    assert repair("그랬군요. 어떤 기분이었어요? 누구와 있었어요?") == "그랬군요. 어떤 기분이었어요?"


def test_repair_drops_false_comfort_sentence_and_emoji():
    fixed = repair("괜찮아질 거예요. 그때 어떤 생각이 들었어요? 😊")
    assert fixed == "그때 어떤 생각이 들었어요?"


# ── 재생성 흐름 ─────────────────────────────────────────────────────

def test_verify_passes_through_good_reply():
    result = verify(GOOD, regenerate=lambda f: pytest.fail("should not regenerate"))
    assert result.reply == GOOD
    assert result.passed_first and not result.regenerated


def test_verify_regenerates_once_with_feedback():
    seen = {}

    def regenerate(feedback):
        seen["feedback"] = feedback
        return GOOD

    result = verify("지난번에도 그러셨죠. 오늘은요?", regenerate=regenerate)

    assert result.reply == GOOD
    assert result.regenerated and not result.fallback
    assert "지난 상담이나 예전 대화를 기억하는 것처럼" in seen["feedback"]


def test_verify_falls_back_when_hard_violation_remains():
    result = verify(
        "우울증 같아요.", regenerate=lambda f: "공황장애일 수도 있어요."
    )
    assert result.reply == SAFE_REPLY
    assert result.fallback


def test_verify_repairs_when_only_soft_violation_remains():
    result = verify(
        "어떤 기분이었어요? 누구와 있었어요?",
        regenerate=lambda f: "그랬군요. 어떤 기분이었어요? 그때 어디였어요?",
    )
    assert result.reply == "그랬군요. 어떤 기분이었어요?"
    assert result.repaired and result.final_violations == []


def test_verify_survives_regeneration_error():
    def boom(feedback):
        raise RuntimeError("network")

    result = verify("어떤 기분이었어요? 누구와요?", regenerate=boom)
    assert result.reply == "어떤 기분이었어요?"
    assert not result.regenerated and result.repaired


# ── API 연결 ─────────────────────────────────────────────────────────

def test_counsel_turn_regenerates_bad_reply(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()
    calls = []

    def chat(system_prompt, messages):
        calls.append(system_prompt)
        if len(calls) == 1:
            return "지난번에도 비슷한 일이 있었죠. 우울증일 수 있어요."
        return GOOD

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)
    response = client.post("/counsel/turn", json={"user_text": "회의에서 서운했어"})

    assert response.status_code == 200
    assert response.json()["reply"] == GOOD
    assert len(calls) == 2
    assert "[응답 재작성 지시" in calls[1]