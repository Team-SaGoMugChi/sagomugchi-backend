"""일기 기록(Step2 확인)이 끝난 뒤 영상(성진)·상담(다경) 파트에 넘길 JSON을 만든다.

영상용 `oddo.diary_emotion.v1`
    재영이 2026-09-26 확정한 v0-sample 틀(diary·emotion_overall·scenes·turning_points·
    sentences)을 유지하고, 대화형 말하기로 새로 생긴 재료(정제 일기·요약·대화 칸)를 더했다.
    장면 규칙은 scripts/diary_emotion_test.py의 to_video_json과 같다.
      - 문장별 감정은 KOTE로 따로 계산한다(일기 전체를 한 번에 넣으면 한 감정만 남는다).
      - 장면 = 톤이 같은 연속 문장. 중립 문장은 앞뒤 톤이 같으면 앞 장면에 붙이고, 다르면
        다음 장면의 전환 문장으로 붙인다.
    v0과 달라진 점
      - 문장별 초 단위 시간이 없다. 대화형은 차례별로 녹음해 이어 붙이고 STT가 텍스트만
        돌려준다. 시간 대신 turn(몇 번째 답인지)을 넣고, 가중 평균은 문장 길이(글자 수)로 한다.
      - emotion_overall은 Step2 결합 결과(텍스트·표정·음성)를 그대로 쓴다 — 앱 화면·저장값과 같다.
    원문(diary.transcript)은 다듬지 않은 사용자 답변이다(감정 분석 입력과 같다). 정제한 일기는
    diary.diary_text에 따로 넣는다.

상담용 `oddo.counsel_context.v1`
    /counsel/turn 요청 필드 이름(emotions·signals·diary_summary·incongruent)을 그대로 써서
    그대로 옮겨 담을 수 있게 하고, 상담에 쓸 맥락(대화 칸·정제 일기·감정 흐름)을 더했다.
"""

import logging
import re
from collections.abc import Sequence

from app.models.diary_handoff import HandoffRequest
from app.services.multimodal_fusion import text_valence
from app.services.text_emotion import EMOTION_LABELS, TextEmotionClassifier, get_text_emotion_classifier

logger = logging.getLogger(__name__)

VIDEO_SCHEMA = "oddo.diary_emotion.v1"
COUNSEL_SCHEMA = "oddo.counsel_context.v1"
NEUTRAL = "중립"
TOP_EMOTION_MIN = 10  # 장면·전체의 대표 감정으로 칠 최소 점수(0~100)
# 문장별 감정으로 인정할 최소 확신도. 대화형은 사실만 답한 짧은 문장("스터디룸이에요")이 많은데,
# KOTE가 여기에 '기쁨'을 확신도 0.68~0.75로 붙여 감정 흐름이 들쭉날쭉해졌다(감정이 담긴 문장은
# 0.91~0.97). 샘플 한 편으로 정한 잠정값이라 평가셋으로 다시 맞춘다.
SENTENCE_MIN_CONFIDENCE = 0.8

VIDEO_GUIDE = {
    "목적": "대화형 일기 1편의 원문·정제 일기와 감정 분석 결과. 숏폼 영상의 장면 구성·분위기 결정에 쓰는 입력.",
    "만들어지는 때": "사용자가 Step2(확인하기)에서 '저장하고 다음 단계'를 누를 때. 같은 날 다시 누르면 덮어쓴다.",
    "diary.transcript": "사용자가 탄카츄와 대화하며 한 말(STT 원문, 차례마다 줄바꿈). 다듬지 않았다. 감정 분석 입력과 같다.",
    "diary.diary_text": "대화를 일기 한 편으로 정제하고 사용자가 확인·수정한 글(보여주기용). 없으면 null.",
    "diary.summary": "한두 문장 요약. 없으면 null.",
    "diary.slots": "대화에서 모은 칸(육하원칙 + 그때 기분·기분 변화·지금 기분). 사용자가 말한 대로이고 말하지 않은 칸은 null.",
    "turn": "몇 번째 답인지(1부터). 대화형은 차례별로 녹음해 문장별 초 단위 시간이 없어서 시간 대신 쓴다.",
    "emotion_scores": "감정 6종(기쁨·슬픔·분노·불안·상처·당황) 점수 0~100. 0인 감정은 생략.",
    "tone": "긍정 / 중립 / 부정. 영상 분위기(밝음·잔잔함·가라앉음)에 대응.",
    "intensity": "감정 강도 0~100. 높을수록 감정이 뚜렷하다.",
    "emotion_overall": "Step2 감정 분석 결과(텍스트·표정·음성 결합) — 앱 화면·저장값과 같다.",
    "emotion_overall.arc": "장면 순서대로 본 감정 흐름 한 줄.",
    "emotion_overall.signals": "평소(baseline)보다 뚜렷하게 달라진 표정·목소리를 문장으로. 표정 연출 힌트.",
    "emotion_overall.incongruent": "말한 감정과 표정·목소리가 어긋난 경우 true.",
    "scenes": "톤이 같은 연속 문장을 묶은 장면 후보. 감정이 바뀌는 곳에서 나뉜다.",
    "turning_points": "감정 톤이 바뀌는 곳. 영상에서 분위기·음악·표정이 바뀌어야 하는 곳.",
    "sentences": "문장별 텍스트 감정(KOTE). 감정이 뚜렷하지 않은 문장(확신도 0.8 미만, 예: 사실만 답한 문장)이나 계산하지 못한 문장은 emotion이 null이고 tone은 중립.",
    "한계": "감정 분석 가중치는 이론 기반 잠정값이다. 표정·목소리 변화가 작으면 감정은 주로 말한 내용(텍스트)에서 나온다.",
}

COUNSEL_GUIDE = {
    "목적": "상담(Step4) 전에 오늘 일기에서 알게 된 것. 상담봇이 사용자의 상태를 알고 대화를 시작하게 한다.",
    "만들어지는 때": "사용자가 Step2(확인하기)에서 '저장하고 다음 단계'를 누를 때. 같은 날 다시 누르면 덮어쓴다.",
    "상담 API 연결": "emotions·signals·diary_summary·incongruent는 /counsel/turn 요청의 같은 이름 필드에 그대로 넣으면 된다.",
    "emotions": "감정 6종 점수 0~100(Step2 텍스트·표정·음성 결합 결과).",
    "signals": "평소(baseline)보다 뚜렷하게 달라진 표정·목소리를 문장으로.",
    "diary_summary": "일기 요약 한두 문장. 요약이 없으면 정제 일기, 그것도 없으면 원문.",
    "incongruent": "말한 감정과 표정·목소리가 어긋난 경우 true — 상담에서 조심스럽게 짚어볼 곳.",
    "diary_text": "대화를 정제하고 사용자가 확인한 일기. 없으면 null.",
    "slots": "대화에서 모은 칸(육하원칙 + 그때 기분·기분 변화·지금 기분). 사용자가 말한 대로.",
    "emotion_arc": "감정 흐름 한 줄. turning_points는 감정 톤이 바뀐 문장.",
}


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.?!])\s+", text.strip()) if part.strip()]


def tone_of(scores_0_100: dict[str, float]) -> str:
    value = text_valence({label: score / 100 for label, score in scores_0_100.items()})
    return "긍정" if value > 0.2 else "부정" if value < -0.2 else NEUTRAL


def _sentence(index: int, turn: int, text: str, classifier: TextEmotionClassifier | None) -> dict:
    sentence = {"index": index, "turn": turn, "text": text, "emotion": None, "tone": NEUTRAL,
                "intensity": 0, "emotion_scores": {}}
    if classifier is None:
        return sentence
    result = classifier.classify(text)
    if result.dominant_emotion is None or result.confidence < SENTENCE_MIN_CONFIDENCE:
        return sentence
    scores = {label: round(score * 100, 1) for label, score in result.scores.items() if score > 0}
    sentence.update(
        emotion=result.dominant_emotion,
        tone=tone_of(scores),
        intensity=max(0, min(100, round(result.confidence * 100))),
        emotion_scores=scores,
    )
    return sentence


def build_sentences(transcript: str, classifier: TextEmotionClassifier | None) -> list[dict]:
    """차례(줄)마다 문장부호로 나눠 문장별 감정을 붙인다."""
    sentences = []
    turns = [line for line in transcript.splitlines() if line.strip()]
    for turn, line in enumerate(turns, start=1):
        for text in _split_sentences(line):
            sentences.append(_sentence(len(sentences) + 1, turn, text, classifier))
    return sentences


def _weight(sentence: dict) -> int:
    return len(sentence["text"])


def _weighted_scores(sentences: Sequence[dict]) -> dict[str, float]:
    """문장별 점수를 문장 길이로 가중 평균 — 일기 전체를 한 번에 분류하면 가장 강한 감정 하나만 남는다."""
    counted = [s for s in sentences if s["emotion"]]
    total = sum(_weight(s) for s in counted) or 1
    return {label: round(sum(s["emotion_scores"].get(label, 0.0) * _weight(s) for s in counted) / total, 1)
            for label in EMOTION_LABELS}


def _top_labels(scores: dict[str, float], n: int = 2) -> list[str]:
    return [label for label, score in sorted(scores.items(), key=lambda kv: -kv[1])
            if score >= TOP_EMOTION_MIN][:n]


def _avg_intensity(sentences: Sequence[dict]) -> int:
    total = sum(_weight(s) for s in sentences) or 1
    return round(sum(s["intensity"] * _weight(s) for s in sentences) / total)


def _group_scenes(sentences: Sequence[dict]) -> list[list[dict]]:
    """톤이 같은 연속 문장을 묶는다. 중립 문장은 앞뒤 톤이 같으면 앞 장면에 붙이고(감정 없는 문장
    조각이 장면을 쪼개지 않게), 다르면 다음 장면의 전환 문장으로 붙인다."""
    groups: list[dict] = []
    for i, s in enumerate(sentences):
        if s["tone"] == NEUTRAL and groups:
            nxt = next((x["tone"] for x in sentences[i + 1:] if x["tone"] != NEUTRAL), None)
            if nxt is None or nxt == groups[-1]["tone"]:
                groups[-1]["items"].append(s)
            else:
                groups.append({"tone": nxt, "items": [s]})
            continue
        if groups and groups[-1]["tone"] in (s["tone"], NEUTRAL):
            groups[-1]["tone"] = s["tone"]
            groups[-1]["items"].append(s)
        else:
            groups.append({"tone": s["tone"], "items": [s]})
    return [g["items"] for g in groups]


def _scenes(sentences: Sequence[dict]) -> list[dict]:
    scenes = []
    for order, items in enumerate(_group_scenes(sentences), start=1):
        scores = _weighted_scores(items)
        scenes.append({
            "order": order,
            "turns": sorted({s["turn"] for s in items}),
            "tone": tone_of(scores),
            "emotions": _top_labels(scores),
            "intensity": _avg_intensity(items),
            "sentence_indexes": [s["index"] for s in items],
            "text": " ".join(s["text"] for s in items),
        })
    return scenes


def _turning_points(scenes: Sequence[dict], sentences: Sequence[dict]) -> list[dict]:
    by_index = {s["index"]: s for s in sentences}
    points = []
    for before, after in zip(scenes, scenes[1:]):
        if before["tone"] == after["tone"]:
            continue
        first = by_index[after["sentence_indexes"][0]]
        points.append({"turn": first["turn"], "sentence_index": first["index"],
                       "from": before["tone"], "to": after["tone"], "sentence": first["text"]})
    return points


def _arc(scenes: Sequence[dict]) -> str:
    return " → ".join(f'{s["tone"]}({", ".join(s["emotions"])})' if s["emotions"] else s["tone"] for s in scenes)


def _classifier() -> TextEmotionClassifier | None:
    try:
        return get_text_emotion_classifier()
    except Exception as exc:
        # 문장별 감정 없이도 원문·칸·전체 감정은 넘길 수 있다.
        logger.warning("diary handoff without sentence emotions: %s", type(exc).__name__)
        return None


def _title_hint(req: HandoffRequest, sentences: Sequence[dict]) -> str | None:
    what = req.slots.get("무엇을")
    if what and what.strip():
        return what.strip()
    if req.summary and req.summary.strip():
        return req.summary.strip()
    return sentences[0]["text"] if sentences else None


def build_handoff(req: HandoffRequest) -> tuple[dict, dict]:
    try:
        sentences = build_sentences(req.transcript, _classifier())
    except Exception as exc:
        logger.warning("diary handoff sentence emotions failed: %s", type(exc).__name__)
        sentences = build_sentences(req.transcript, None)
    scenes = _scenes(sentences)
    turning_points = _turning_points(scenes, sentences)
    arc = _arc(scenes)

    scores = {label: req.emotion.scores[label] for label in EMOTION_LABELS if req.emotion.scores.get(label, 0) > 0}
    overall_scores = dict(sorted(scores.items(), key=lambda kv: -kv[1]))
    slots = {name: (value.strip() if isinstance(value, str) and value.strip() else None)
             for name, value in req.slots.items()}
    diary_text = req.diary_text.strip() if req.diary_text and req.diary_text.strip() else None
    summary = req.summary.strip() if req.summary and req.summary.strip() else None

    video = {
        "설명": VIDEO_GUIDE,
        "schema": VIDEO_SCHEMA,
        "diary": {
            "date": req.date,
            "title_hint": _title_hint(req, sentences),
            "turn_count": max((s["turn"] for s in sentences), default=0),
            "transcript": req.transcript,
            "diary_text": diary_text,
            "summary": summary,
            "slots": slots,
        },
        "emotion_overall": {
            "keywords": req.emotion.keywords,
            "scores": overall_scores,
            "tone": tone_of(overall_scores),
            "intensity": req.emotion.intensity,
            "arc": arc,
            "signals": req.emotion.signals,
            "incongruent": req.emotion.incongruent,
        },
        "scenes": scenes,
        "turning_points": turning_points,
        "sentences": sentences,
    }
    counsel = {
        "설명": COUNSEL_GUIDE,
        "schema": COUNSEL_SCHEMA,
        "date": req.date,
        "emotions": overall_scores,
        "signals": req.emotion.signals,
        "diary_summary": summary or diary_text or req.transcript,
        "incongruent": req.emotion.incongruent,
        "diary_text": diary_text,
        "slots": slots,
        "emotion_arc": arc,
        "turning_points": [{"from": p["from"], "to": p["to"], "sentence": p["sentence"]} for p in turning_points],
    }
    return video, counsel
