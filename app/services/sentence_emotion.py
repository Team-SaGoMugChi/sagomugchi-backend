"""일기 텍스트 감정을 문장별로 계산해 문장 길이로 가중 평균한다.

일기 전체를 KOTE에 한 번에 넣으면 가장 강한 감정 하나만 문턱값(0.4)을 넘고 나머지는 잘려서,
감정이 섞인 일기도 한 감정만 남는다(2026-10-05 실기기 테스트: 긴장·막막함이 섞인 발표 일기가
`기쁨 100`). 문장마다 따로 매기면 문장별로 다른 감정이 살아남는다.

Step2 감정 분석(fusion.fuse_emotion)과 전달 JSON(diary_handoff)이 같은 문장 나누기를 쓴다.
"""

import re
from collections.abc import Iterator

from app.services.text_emotion import EMOTION_LABELS, TextEmotionClassifier, TextEmotionResult


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.?!])\s+", text.strip()) if part.strip()]


def iter_turn_sentences(transcript: str) -> Iterator[tuple[int, str]]:
    """차례(줄)마다 문장부호로 나눈 문장을 (차례 번호, 문장)으로 돌려준다. 차례는 1부터."""
    turns = [line for line in transcript.splitlines() if line.strip()]
    for turn, line in enumerate(turns, start=1):
        for sentence in split_sentences(line):
            yield turn, sentence


def classify_by_sentence(classifier: TextEmotionClassifier, text: str) -> TextEmotionResult:
    """문장별 6종 점수를 문장 길이(글자 수)로 가중 평균한다.

    판단 불가인 문장은 평균에서 뺀다. 확신도도 같은 가중 평균이다(감정 강도 계산에 쓰인다).
    전달 JSON의 문장 확신도 기준(SENTENCE_MIN_CONFIDENCE)은 장면을 나누는 용도라 여기서는 쓰지
    않는다 — 쓰면 감정이 담겼지만 확신도가 0.73~0.80인 부정 문장이 빠져 다시 한 감정으로 쏠린다.
    """
    sentences = [sentence for _, sentence in iter_turn_sentences(text)]
    if not sentences:
        return classifier.classify(text)  # 빈 입력 오류는 분류기가 판단한다
    totals = dict.fromkeys(EMOTION_LABELS, 0.0)
    confidence = 0.0
    weight_sum = 0
    for sentence in sentences:
        result = classifier.classify(sentence)
        if result.dominant_emotion is None:
            continue
        weight = len(sentence)
        for label in EMOTION_LABELS:
            totals[label] += result.scores.get(label, 0.0) * weight
        confidence += result.confidence * weight
        weight_sum += weight
    if weight_sum == 0:
        return TextEmotionResult(dict.fromkeys(EMOTION_LABELS, 0.0), None, 0.0)
    scores = {label: value / weight_sum for label, value in totals.items()}
    return TextEmotionResult(scores, max(scores, key=scores.get), confidence / weight_sum)
