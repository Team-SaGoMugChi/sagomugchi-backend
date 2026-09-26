"""scripts/diary_emotion_test.py의 계산 부분 — 카메라·마이크·CLOVA 없이 검증한다."""

import pytest

from scripts.diary_emotion_test import group_scenes, split_sentences, to_video_json, weighted_scores


def test_sentences_get_times_from_word_timings():
    segment = {
        "start": 0, "end": 5000, "text": "오늘 속상했어요. 그래도 괜찮아요.",
        "words": [[100, 400, "오늘"], [500, 1500, "속상했어요"], [2000, 2600, "그래도"], [2700, 3600, "괜찮아요"]],
    }

    assert split_sentences(segment) == [(0.1, 1.5, "오늘 속상했어요."), (2.0, 3.6, "그래도 괜찮아요.")]


def test_word_count_mismatch_keeps_the_whole_segment():
    segment = {"start": 0, "end": 5000, "text": "하나. 둘.", "words": [[0, 100, "하나"]]}

    assert split_sentences(segment) == [(0.0, 5.0, "하나. 둘.")]


def _sentence(index, start, end, tone, emotion, **scores):
    return {"index": index, "start_sec": start, "end_sec": end, "text": f"문장{index}.", "tone": tone,
            "emotion": emotion, "intensity": 50, "emotion_scores": scores}


def test_overall_is_weighted_by_sentence_length_not_just_the_strongest():
    sentences = [_sentence(0, 0, 3, "부정", "상처", 상처=100.0), _sentence(1, 3, 4, "긍정", "기쁨", 기쁨=100.0)]

    scores = weighted_scores(sentences)

    assert scores["상처"] == pytest.approx(75.0)
    assert scores["기쁨"] == pytest.approx(25.0)


def test_neutral_fragment_between_same_tones_does_not_split_a_scene():
    sentences = [
        _sentence(0, 0, 2, "긍정", "기쁨", 기쁨=100.0),
        _sentence(1, 2, 3, "중립", None),
        _sentence(2, 3, 5, "긍정", "기쁨", 기쁨=100.0),
        _sentence(3, 5, 6, "부정", "상처", 상처=100.0),
    ]

    assert [[s["index"] for s in scene] for scene in group_scenes(sentences)] == [[0, 1, 2], [3]]


def test_neutral_sentence_before_a_change_opens_the_next_scene():
    sentences = [
        _sentence(0, 0, 2, "부정", "상처", 상처=100.0),
        _sentence(1, 2, 3, "중립", "기쁨", 기쁨=50.0, 불안=50.0),
        _sentence(2, 3, 5, "긍정", "기쁨", 기쁨=100.0),
    ]

    assert [[s["index"] for s in scene] for scene in group_scenes(sentences)] == [[0], [1, 2]]


def test_video_json_has_scenes_turning_points_and_counsel_fields():
    analysis = {
        "diary": {"transcript": "문장0. 문장1.", "duration_sec": 6.0},
        "emotion_overall": {"signals": ["목소리 높이가 평소보다 낮음"], "incongruent": True,
                            "incongruence_sources": ["voice"]},
        "timeline": [
            {**_sentence(0, 0, 3, "부정", "상처", 상처=100.0), "face_valence": None, "voice_arousal": None, "incongruent": False},
            {**_sentence(1, 3, 6, "긍정", "기쁨", 기쁨=100.0), "face_valence": None, "voice_arousal": None, "incongruent": False},
        ],
    }

    video = to_video_json(analysis)

    assert video["schema"] == "oddo.diary_emotion.v0-sample"
    assert [s["tone"] for s in video["scenes"]] == ["부정", "긍정"]
    assert video["turning_points"] == [{"at_sec": 3, "from": "부정", "to": "긍정", "sentence": "문장1."}]
    assert video["emotion_overall"]["arc"] == "부정(상처) → 긍정(기쁨)"
    assert video["emotion_overall"]["signals"] == ["목소리 높이가 평소보다 낮음"]
    assert video["emotion_overall"]["incongruence_sources"] == ["voice"]
    assert "self_report" not in video
