import pytest

from app.services.modality_emotion import FaceEmotion, VoiceArousal
from app.services.multimodal_fusion import (
    AROUSAL_SIGN,
    MIN_MULTIPLIER,
    VALENCE_SIGN,
    fuse_multimodal,
    text_valence,
)
from app.services.text_emotion import EMOTION_LABELS, TextEmotionResult


def _text(dominant: str | None = None, confidence: float = 0.8, **scores: float) -> TextEmotionResult:
    full = {label: scores.get(label, 0.0) for label in EMOTION_LABELS}
    return TextEmotionResult(full, dominant, confidence)


def _face(valence: float = 0.0, z: dict[str, float] | None = None, **scores: float) -> FaceEmotion:
    return FaceEmotion(
        scores={label: scores.get(label, 0.0) for label in EMOTION_LABELS},
        valence=valence,
        z=z or {},
    )


# "너무 속상했어요. 그래도 위로가 됐어요." — 실제 KOTE 결과
_MIXED = _text("기쁨", 0.878, 기쁨=0.484, 슬픔=0.277, 불안=0.239)
_SAD_FACE = _face(-0.7, {"au15": 6.0, "au17": 4.0}, 슬픔=0.52, 상처=0.52, 분노=0.25, 불안=0.15)


def test_sign_tables_cover_the_six_team_emotions():
    assert set(VALENCE_SIGN) == set(EMOTION_LABELS)
    assert set(AROUSAL_SIGN) == set(EMOTION_LABELS)


def test_text_only_keeps_text_scores():
    result = fuse_multimodal(_MIXED)

    assert result.emotion_scores == pytest.approx({"기쁨": 48.4, "슬픔": 27.7, "분노": 0, "불안": 23.9, "상처": 0, "당황": 0})
    assert result.emotion_keywords == ["기쁨", "슬픔"]
    assert result.emotion_intensity == 88
    assert result.modalities == ["text"]
    assert result.incongruent is False


def test_neutral_face_and_calm_voice_do_not_change_the_ranking():
    result = fuse_multimodal(_MIXED, _face(), VoiceArousal(0.0, {}))

    assert result.emotion_keywords == ["기쁨", "슬픔"]
    assert result.emotion_scores["기쁨"] == pytest.approx(48.4, abs=0.1)


def test_sad_face_turns_a_mixed_diary_into_sadness():
    result = fuse_multimodal(_MIXED, _SAD_FACE)

    assert result.emotion_keywords[0] == "슬픔"
    assert result.emotion_scores["기쁨"] < 48.4
    assert "입꼬리가 평소보다 처짐" in result.signals


def test_face_cannot_create_an_emotion_the_text_did_not_mention():
    result = fuse_multimodal(_MIXED, _SAD_FACE)

    assert result.emotion_scores["상처"] == 0  # 얼굴 근거 0.52여도 텍스트가 0이면 0


def test_arousal_separates_high_and_low_arousal_emotions():
    split = _text("분노", 0.7, 분노=0.5, 슬픔=0.5)

    tense = fuse_multimodal(split, voice=VoiceArousal(0.8, {}))
    flat = fuse_multimodal(split, voice=VoiceArousal(-0.8, {}))

    assert tense.emotion_keywords[0] == "분노"
    assert flat.emotion_keywords[0] == "슬픔"


_JOY_ONLY = _text("기쁨", 0.8, 기쁨=1.0)  # "오늘 진짜 괜찮았어. 다 좋았어."
_FLAT_VOICE = VoiceArousal(-0.6, {"pitchMean": -4.7, "energyMean": -2.5})  # 괜찮은 척 녹음 실측


def test_positive_words_with_a_clearly_sad_face_are_incongruent():
    result = fuse_multimodal(_JOY_ONLY, _SAD_FACE)

    assert result.incongruent is True
    assert result.incongruence_sources == ["face"]
    assert result.emotion_scores["기쁨"] == 100  # 결과는 텍스트를 따르되 불일치로 알린다


def test_negative_words_with_a_clearly_happy_face_are_incongruent():
    sad_words = _text("슬픔", 0.8, 슬픔=1.0)

    assert fuse_multimodal(sad_words, _face(0.6, 기쁨=0.6)).incongruence_sources == ["face"]


def test_positive_words_with_a_sunken_voice_are_incongruent():
    # 괜찮은 척 1회차: 표정은 거의 무표정(−0.07)이었지만 목소리가 가라앉았다
    result = fuse_multimodal(_JOY_ONLY, _face(-0.07), _FLAT_VOICE)

    assert result.incongruent is True
    assert result.incongruence_sources == ["voice"]


def test_face_and_voice_can_both_disagree():
    assert fuse_multimodal(_JOY_ONLY, _SAD_FACE, _FLAT_VOICE).incongruence_sources == ["face", "voice"]


def test_real_joy_with_a_near_baseline_voice_is_not_incongruent():
    # 기쁨 녹음 실측: 표정 긍정도 +0.42, 흥분도 −0.05
    result = fuse_multimodal(_JOY_ONLY, _face(0.42, 기쁨=0.5), VoiceArousal(-0.05, {}))

    assert result.incongruent is False


def test_calm_voice_with_a_clearly_happy_face_is_not_incongruent():
    # 차분하게 말해도 표정이 뚜렷하게 밝으면 목소리만으로 불일치라 하지 않는다
    assert fuse_multimodal(_JOY_ONLY, _face(0.3, 기쁨=0.4), _FLAT_VOICE).incongruent is False


def test_voice_alone_can_flag_when_no_face_is_found():
    assert fuse_multimodal(_JOY_ONLY, None, _FLAT_VOICE).incongruence_sources == ["voice"]


def test_negative_words_with_a_tense_voice_are_not_incongruent():
    # 화난 말에 높은 흥분도는 자연스럽다
    angry = _text("분노", 0.8, 분노=1.0)

    assert fuse_multimodal(angry, _face(-0.4, 분노=0.4), VoiceArousal(0.8, {})).incongruent is False


def test_mixed_words_are_never_incongruent():
    assert abs(text_valence(_MIXED.scores)) < 0.3
    assert fuse_multimodal(_MIXED, _SAD_FACE).incongruent is False


def test_undecidable_text_stays_undecidable_but_keeps_signals():
    result = fuse_multimodal(_text(None, 0.0), _SAD_FACE, VoiceArousal(-0.9, {"pitchMean": -3.0}))

    assert result.emotion_keywords == []
    assert result.emotion_intensity == 0
    assert all(value == 0 for value in result.emotion_scores.values())
    assert "목소리 높이가 평소보다 낮음" in result.signals
    assert result.modalities == ["text", "face", "voice"]


def test_extreme_inputs_keep_scores_valid():
    extreme = _face(-5.0, **{label: 5.0 for label in EMOTION_LABELS})
    result = fuse_multimodal(_MIXED, extreme, VoiceArousal(-5.0, {}))

    assert sum(result.emotion_scores.values()) == pytest.approx(100, abs=0.5)
    assert all(value >= 0 for value in result.emotion_scores.values())
    assert 0 <= result.emotion_intensity <= 100
    assert MIN_MULTIPLIER > 0
