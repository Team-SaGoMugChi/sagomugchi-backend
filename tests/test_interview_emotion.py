from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.interview_emotion import analyze_answer, emotion_keywords, keyword_name
from app.services.kote_emotion import EXPECTED_LABELS, TextEmotionUnavailable, project_six
from app.services.text_emotion import EMOTION_LABELS, TextEmotionClassifier, TextEmotionResult

client = TestClient(app)

ANGRY = "팀장이 내 말을 끊어서 짜증났어."
UNFAIR = "내 잘못도 아닌데 혼나서 억울했어."
FACT = "회의실이었어."


def native(**values):
    return dict.fromkeys(EXPECTED_LABELS, 0.01) | values


class _Kote(TextEmotionClassifier):
    """문장마다 정해 둔 KOTE 원래 점수를 6종으로 묶어 돌려준다."""

    def classify(self, text: str) -> TextEmotionResult:
        if "짜증" in text:
            return project_six(native(**{"짜증": 0.9, "화남/분노": 0.7, "불평/불만": 0.5}))
        if "억울" in text:
            return project_six(native(**{"불평/불만": 0.8, "서러움": 0.6, "패배/자기혐오": 0.45}))
        return project_six(native(**{"없음": 0.9}))


def test_answer_keeps_six_scores_and_ranks_fine_keywords():
    result = analyze_answer(_Kote(), f"{ANGRY} {UNFAIR} {FACT}")

    assert set(result.scores) == set(EMOTION_LABELS)
    assert sum(result.scores.values()) == pytest.approx(1.0)
    assert result.dominant_emotion == "분노"
    # 문장별 최고값으로 줄 세운다: 짜증 0.9, 불평/불만 0.8(두 문장 중 높은 값), 화남/분노 0.7, 서러움 0.6
    assert result.keywords == ["짜증", "불평", "화남", "서러움"]


def test_weak_and_no_emotion_labels_are_not_keywords():
    assert emotion_keywords({"없음": 0.95, "짜증": 0.39, "슬픔": 0.4}) == ["슬픔"]


def test_answer_without_emotion_has_no_keywords():
    result = analyze_answer(_Kote(), FACT)

    assert result.dominant_emotion is None
    assert result.scores == dict.fromkeys(EMOTION_LABELS, 0.0)
    assert result.keywords == []


def test_classifier_without_fine_labels_gives_no_keywords():
    class SixOnly(TextEmotionClassifier):
        def classify(self, text: str) -> TextEmotionResult:
            return TextEmotionResult({**dict.fromkeys(EMOTION_LABELS, 0.0), "기쁨": 1.0}, "기쁨", 0.9)

    result = analyze_answer(SixOnly(), "좋았어.")

    assert result.dominant_emotion == "기쁨"
    assert result.keywords == []


@pytest.mark.parametrize(
    ("label", "name"),
    [("화남/분노", "화남"), ("흐뭇함(귀여움/예쁨)", "흐뭇함"), ("부담/안_내킴", "부담"), ("패배/자기혐오", "자기혐오"), ("짜증", "짜증")],
)
def test_keyword_name_reads_naturally(label, name):
    assert keyword_name(label) == name


def test_emotion_endpoint_returns_answer_emotion(monkeypatch):
    monkeypatch.setattr("app.api.routes.diary_interview.get_text_emotion_classifier", _Kote)

    response = client.post("/diary/interview/emotion", json={"user_text": ANGRY})

    assert response.status_code == 200
    body = response.json()
    assert body["dominant_emotion"] == "분노"
    assert set(body["scores"]) == set(EMOTION_LABELS)
    assert body["keywords"] == ["짜증", "화남", "불평"]


def test_emotion_endpoint_reports_model_unavailability(monkeypatch):
    def fail(text):
        raise TextEmotionUnavailable("private cache path")

    monkeypatch.setattr(
        "app.api.routes.diary_interview.get_text_emotion_classifier", lambda: SimpleNamespace(classify=fail)
    )

    response = client.post("/diary/interview/emotion", json={"user_text": ANGRY})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "text_emotion_unavailable"
    assert "private cache path" not in response.text


@pytest.mark.parametrize("text", ["", "  \n "], ids=["empty", "blank"])
def test_emotion_endpoint_rejects_blank_answer(text):
    assert client.post("/diary/interview/emotion", json={"user_text": text}).status_code == 422
