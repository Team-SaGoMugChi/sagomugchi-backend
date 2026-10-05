import pytest

from app.services import fusion
from app.services.modality_emotion import FaceEmotion
from app.services.sentence_emotion import classify_by_sentence, iter_turn_sentences
from app.services.text_emotion import EMOTION_LABELS, TextEmotionClassifier, TextEmotionResult

# 문장 길이(글자 수): 10 / 10 / 5
JOY = "칭찬받아 뿌듯했어."
WORRY = "민폐일까 봐 걱정."
FACT = "학교였어."


def _result(confidence=0.95, **scores):
    full = {label: scores.get(label, 0.0) for label in EMOTION_LABELS}
    dominant = max(full, key=full.get) if scores else None
    return TextEmotionResult(scores=full, dominant_emotion=dominant, confidence=confidence if dominant else 0.0)


class _Classifier(TextEmotionClassifier):
    def __init__(self):
        self.calls = []

    def classify(self, text: str) -> TextEmotionResult:
        if not text.strip():
            raise ValueError("text must not be blank")
        self.calls.append(text)
        if "뿌듯" in text:
            return _result(기쁨=1.0)
        if "걱정" in text:
            # 감정이 담겼지만 확신도가 낮은 문장도 평균에 넣는다.
            return _result(confidence=0.75, 불안=0.6, 상처=0.4)
        return _result()


def test_iter_turn_sentences_splits_turns_then_sentences():
    transcript = "오늘 발표했어. 떨렸어!\n\n칭찬받았어?\n끝"

    assert list(iter_turn_sentences(transcript)) == [
        (1, "오늘 발표했어."),
        (1, "떨렸어!"),
        (2, "칭찬받았어?"),
        (3, "끝"),
    ]


def test_mixed_diary_keeps_every_emotion_weighted_by_length():
    classifier = _Classifier()

    result = classify_by_sentence(classifier, f"{JOY} {WORRY}\n{FACT}")

    assert classifier.calls == [JOY, WORRY, FACT]
    # 감정 없는 문장(FACT)은 빼고 10:10으로 평균
    assert result.scores["기쁨"] == pytest.approx(0.5)
    assert result.scores["불안"] == pytest.approx(0.3)
    assert result.scores["상처"] == pytest.approx(0.2)
    assert sum(result.scores.values()) == pytest.approx(1.0)
    assert result.dominant_emotion == "기쁨"
    assert result.confidence == pytest.approx((0.95 * 10 + 0.75 * 10) / 20)


def test_single_emotion_diary_matches_sentence_result():
    result = classify_by_sentence(_Classifier(), f"{JOY}\n{FACT}")

    assert result.scores["기쁨"] == pytest.approx(1.0)
    assert result.dominant_emotion == "기쁨"
    assert result.confidence == pytest.approx(0.95)


def test_diary_without_emotional_sentence_is_undetermined():
    result = classify_by_sentence(_Classifier(), f"{FACT} {FACT}")

    assert result.dominant_emotion is None
    assert result.scores == dict.fromkeys(EMOTION_LABELS, 0.0)
    assert result.confidence == 0.0


def test_blank_text_is_left_to_classifier():
    with pytest.raises(ValueError):
        classify_by_sentence(_Classifier(), " \n ")


def test_step2_fusion_reports_mixed_emotions(monkeypatch):
    monkeypatch.setattr(fusion, "get_text_emotion_classifier", _Classifier)

    result = fusion.fuse_emotion(f"{JOY}\n{WORRY}", {}, {})

    assert result.emotion_keywords == ["기쁨", "불안"]
    assert result.emotion_scores == {"기쁨": 50.0, "슬픔": 0.0, "분노": 0.0, "불안": 30.0, "상처": 20.0, "당황": 0.0}


def test_face_evidence_now_shifts_mixed_text_scores(monkeypatch):
    """텍스트가 한 감정뿐이면 표정 보정을 곱해도 다시 100%가 되지만, 섞여 있으면 비중이 움직인다."""
    monkeypatch.setattr(fusion, "get_text_emotion_classifier", _Classifier)
    worried_face = FaceEmotion(scores={**dict.fromkeys(EMOTION_LABELS, 0.0), "불안": 0.5}, valence=0.0, z={})

    text_only = fusion.fuse_emotion(f"{JOY}\n{WORRY}", {}, {})
    with_face = fusion.fuse_emotion(f"{JOY}\n{WORRY}", {}, {}, face=worried_face)

    assert with_face.emotion_scores["불안"] > text_only.emotion_scores["불안"]
    assert with_face.emotion_scores["기쁨"] < text_only.emotion_scores["기쁨"]
