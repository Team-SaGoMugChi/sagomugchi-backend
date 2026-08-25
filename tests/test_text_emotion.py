import pytest

from app.services.text_emotion import EMOTION_LABELS, KeywordTextEmotionClassifier


def test_keyword_classifier_detects_joy():
    result = KeywordTextEmotionClassifier().classify("오늘 정말 행복하고 기쁜 하루였어")

    assert result.dominant_emotion == "기쁨"
    assert result.scores["기쁨"] > 0
    assert sum(result.scores.values()) == pytest.approx(1.0)


def test_keyword_classifier_detects_anxiety():
    result = KeywordTextEmotionClassifier().classify("너무 불안하고 걱정돼서 잠을 못 잤어")

    assert result.dominant_emotion == "불안"


def test_keyword_classifier_falls_back_to_uniform_when_no_keywords_match():
    result = KeywordTextEmotionClassifier().classify("오늘은 카페에 가서 커피를 마셨다")

    assert all(score == pytest.approx(1 / len(EMOTION_LABELS)) for score in result.scores.values())
    assert result.dominant_emotion is None


def test_keyword_classifier_does_not_mistake_negated_good_for_joy():
    # "좋"이 기쁨 키워드에 있으면 "기분이 좋지 않아"(부정문)도 기쁨으로 오분류됨 — 회귀 방지
    result = KeywordTextEmotionClassifier().classify("선생님한테 혼나서 기분이 좋지 않아")

    assert result.dominant_emotion != "기쁨"
