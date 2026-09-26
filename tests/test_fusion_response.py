import math

import pytest
from pydantic import ValidationError

from app.models.fusion import FeatureDeltaOut, FusionResponse


def _valid_response(**overrides):
    values = {
        "emotion_keywords": ["불안"],
        "emotion_scores": {"불안": 72.0},
        "emotion_intensity": 68,
        "text_emotion_scores": {"불안": 0.72},
        "voice_delta": {},
        "face_delta": {},
    }
    values.update(overrides)
    return FusionResponse(**values)


@pytest.mark.parametrize("score", [-0.1, 100.1, math.nan])
def test_fusion_response_rejects_invalid_emotion_score(score):
    with pytest.raises(ValidationError):
        _valid_response(emotion_scores={"불안": score})


@pytest.mark.parametrize("score", [-0.1, 1.1, math.inf])
def test_fusion_response_rejects_invalid_text_probability(score):
    with pytest.raises(ValidationError):
        _valid_response(text_emotion_scores={"불안": score})


@pytest.mark.parametrize("intensity", [-1, 101])
def test_fusion_response_rejects_invalid_intensity(intensity):
    with pytest.raises(ValidationError):
        _valid_response(emotion_intensity=intensity)


def test_feature_delta_rejects_non_finite_values():
    with pytest.raises(ValidationError):
        FeatureDeltaOut(
            baseline_value=220.0,
            current_value=math.nan,
            delta=10.0,
            relative_delta=0.05,
        )
