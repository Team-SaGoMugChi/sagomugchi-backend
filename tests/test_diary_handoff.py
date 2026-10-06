import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.counsel import CounselTurnRequest
from app.models.video import VideoJobRequest
from app.services.video_job import to_diary_input
from app.services import diary_handoff
from app.services.text_emotion import EMOTION_LABELS, TextEmotionClassifier, TextEmotionResult


client = TestClient(app)

TRANSCRIPT = "\n".join([
    "오늘 회의에서 의견이 무시당했어요. 속상했어요.",
    "스터디룸이었어요.",
    "친구가 위로해줘서 기뻤어요.",
])
REQUEST = {
    "date": "2026-09-30",
    "transcript": TRANSCRIPT,
    "diary_text": "오늘 회의에서 내 의견이 무시당했다. 속상했다.",
    "summary": "회의에서 속상했지만 친구 덕에 기뻤던 하루였어요.",
    "slots": {"무엇을": " 회의에서 의견이 무시당함 ", "어디서": "스터디룸", "왜": None},
    "conversation": [
        {"speaker": "oddo", "text": "오늘 어땠어요?"},
        {"speaker": "user", "text": "오늘 회의에서 의견이 무시당했어요. 속상했어요."},
    ],
    "emotion": {
        "keywords": ["상처", "기쁨"],
        "scores": {"상처": 55.0, "기쁨": 30.0, "슬픔": 15.0, "분노": 0.0},
        "intensity": 64,
        "signals": ["목소리가 평소보다 작음"],
        "incongruent": True,
    },
}


def _result(confidence=0.95, **scores):
    full = {label: scores.get(label, 0.0) for label in EMOTION_LABELS}
    dominant = max(full, key=full.get) if scores else None
    return TextEmotionResult(scores=full, dominant_emotion=dominant, confidence=confidence if dominant else 0.0)


class _Classifier(TextEmotionClassifier):
    def classify(self, text: str) -> TextEmotionResult:
        if "무시" in text or "속상" in text:
            return _result(상처=0.7, 슬픔=0.3)
        if "기뻤" in text:
            return _result(기쁨=1.0)
        if "스터디룸" in text:
            # 사실만 답한 문장에 KOTE가 약하게 붙이는 감정 — 중립으로 본다.
            return _result(confidence=0.7, 기쁨=1.0)
        return _result()


@pytest.fixture
def classifier(monkeypatch):
    monkeypatch.setattr(diary_handoff, "get_text_emotion_classifier", lambda: _Classifier())


def _post(payload=REQUEST):
    return client.post("/diary/handoff", json=payload)


def test_handoff_builds_sentences_scenes_and_turning_points(classifier):
    response = _post()

    assert response.status_code == 200
    video = response.json()["video"]
    assert video["schema"] == "oddo.diary_emotion.v1"
    assert [(s["index"], s["turn"], s["emotion"], s["tone"]) for s in video["sentences"]] == [
        (1, 1, "상처", "부정"),
        (2, 1, "상처", "부정"),
        (3, 2, None, "중립"),
        (4, 3, "기쁨", "긍정"),
    ]
    # 중립 문장은 다음 장면(톤이 다름)의 전환 문장으로 붙는다.
    assert [(s["tone"], s["sentence_indexes"], s["turns"]) for s in video["scenes"]] == [
        ("부정", [1, 2], [1]),
        ("긍정", [3, 4], [2, 3]),
    ]
    assert video["scenes"][0]["emotions"] == ["상처", "슬픔"]
    assert video["turning_points"] == [
        {"turn": 2, "sentence_index": 3, "from": "부정", "to": "긍정", "sentence": "스터디룸이었어요."}
    ]
    assert video["emotion_overall"]["arc"] == "부정(상처, 슬픔) → 긍정(기쁨)"


def test_handoff_keeps_the_raw_transcript_and_adds_the_new_diary_material(classifier):
    video = _post().json()["video"]

    diary = video["diary"]
    assert diary["transcript"] == TRANSCRIPT
    assert diary["diary_text"] == "오늘 회의에서 내 의견이 무시당했다. 속상했다."
    assert diary["summary"] == "회의에서 속상했지만 친구 덕에 기뻤던 하루였어요."
    assert diary["slots"] == {"무엇을": "회의에서 의견이 무시당함", "어디서": "스터디룸", "왜": None}
    assert diary["title_hint"] == "회의에서 의견이 무시당함"
    assert diary["turn_count"] == 3
    overall = video["emotion_overall"]
    # 전체 감정은 Step2 결합 결과 그대로 — 0점은 뺀다.
    assert overall["scores"] == {"상처": 55.0, "기쁨": 30.0, "슬픔": 15.0}
    assert overall["keywords"] == ["상처", "기쁨"]
    assert overall["intensity"] == 64
    assert overall["signals"] == ["목소리가 평소보다 작음"]
    assert overall["incongruent"] is True
    assert "설명" in video


def test_handoff_counsel_context_fits_the_counsel_turn_request(classifier):
    counsel = _post().json()["counsel"]

    assert counsel["schema"] == "oddo.counsel_context.v1"
    assert counsel["diary_summary"] == "회의에서 속상했지만 친구 덕에 기뻤던 하루였어요."
    assert counsel["emotion_arc"] == "부정(상처, 슬픔) → 긍정(기쁨)"
    assert counsel["slots"]["어디서"] == "스터디룸"
    # 같은 이름 필드를 그대로 /counsel/turn 요청에 넣을 수 있어야 한다.
    request = CounselTurnRequest(
        user_text="안녕",
        emotions=counsel["emotions"],
        signals=counsel["signals"],
        diary_summary=counsel["diary_summary"],
        incongruent=counsel["incongruent"],
    )
    assert request.emotions == {"상처": 55.0, "기쁨": 30.0, "슬픔": 15.0}


def test_handoff_video_file_rides_along_the_video_job_request(classifier):
    video = _post().json()["video"]

    request = VideoJobRequest(text=TRANSCRIPT, emotion_keywords=["상처"], diary_handoff=video)

    assert request.diary_handoff == video
    # 영상 파트가 전달 JSON을 스토리보드 입력으로 받는다. 일기 글은 정제 일기가 있으면 그것을 쓴다.
    diary = to_diary_input(request)
    assert diary.handoff == video
    assert diary.text == (video["diary"]["diary_text"] or TRANSCRIPT)


def test_video_job_request_without_handoff_still_works():
    assert VideoJobRequest(text="평범한 하루였다.").diary_handoff is None


@pytest.mark.parametrize(
    "summary, diary_text, expected",
    [
        (None, "정제 일기", "정제 일기"),
        ("  ", None, TRANSCRIPT),
    ],
)
def test_handoff_counsel_summary_falls_back(classifier, summary, diary_text, expected):
    counsel = _post({**REQUEST, "summary": summary, "diary_text": diary_text}).json()["counsel"]

    assert counsel["diary_summary"] == expected


def test_handoff_without_sentence_emotions_when_kote_is_unavailable(monkeypatch):
    def unavailable():
        raise RuntimeError("KOTE model missing")

    monkeypatch.setattr(diary_handoff, "get_text_emotion_classifier", unavailable)

    video = _post().json()["video"]

    assert all(s["emotion"] is None and s["tone"] == "중립" for s in video["sentences"])
    assert len(video["scenes"]) == 1
    assert video["turning_points"] == []
    assert video["emotion_overall"]["arc"] == "중립"
    # 문장별 감정이 없어도 전체 감정은 Step2 결과로 넘긴다.
    assert video["emotion_overall"]["keywords"] == ["상처", "기쁨"]


@pytest.mark.parametrize(
    "patch",
    [{"date": "2026/09/30"}, {"transcript": "   "}, {"transcript": ""}],
)
def test_handoff_rejects_invalid_payload(patch):
    assert _post({**REQUEST, **patch}).status_code == 422
