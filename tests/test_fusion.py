import pytest

from app.services.text_emotion import KeywordTextEmotionClassifier

from app.services.baseline_delta import FeatureDelta
from app.services.fusion import fuse_emotion


def test_fuse_emotion_with_joyful_text_and_large_deltas():
    voice_delta = {
        "pitchMean": FeatureDelta(key="pitchMean", baseline_value=200.0, current_value=260.0, delta=60.0, relative_delta=0.3),
        "energyMean": FeatureDelta(key="energyMean", baseline_value=0.1, current_value=0.2, delta=0.1, relative_delta=1.0),
    }
    face_delta = {
        "mouthWidthRatio": FeatureDelta(
            key="mouthWidthRatio", baseline_value=0.5, current_value=0.8, delta=0.3, relative_delta=0.6
        ),
    }

    result = fuse_emotion("오늘 정말 행복하고 기쁜 하루였어", voice_delta, face_delta)

    assert result.emotion_keywords[0] == "기쁨"
    assert result.emotion_scores["기쁨"] > result.emotion_scores["슬픔"]
    assert 0 <= result.emotion_intensity <= 100
    assert result.emotion_intensity > 0


def test_fuse_emotion_with_no_deltas_still_returns_text_driven_result():
    result = fuse_emotion("너무 불안하고 걱정돼서 잠을 못 잤어", {}, {})

    assert result.emotion_keywords[0] == "불안"
    assert result.voice_delta == {}
    assert result.face_delta == {}


@pytest.fixture(autouse=True)
def isolated_text_classifier(monkeypatch):
    monkeypatch.setattr("app.services.fusion.get_text_emotion_classifier", KeywordTextEmotionClassifier)
