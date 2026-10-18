"""일기 말하기 대화(37번 화면)의 답변 하나를 감정 분석한다 — 통화 중 대시보드용.

통화가 끝난 뒤의 Step2 분석(/diary/step2/analyze)과 같은 텍스트 모델·문장 나누기를 쓴다
(KOTE, 문장 길이 가중 — sentence_emotion.py). 음성·표정은 넣지 않는다: 답변 하나는 짧아서
음성 통계가 흔들리고, 멀티모달 결과는 통화 종료 후 Step2에서 그대로 낸다.

질문(/diary/interview/turn)과 따로 부른다. 분석이 늦거나 실패해도 다음 질문은 늦어지지 않는다.
이 결과는 저장하지 않는다 — 보여주기용이고, 기록에 남는 감정은 Step2 결과다.
"""

from dataclasses import dataclass

from app.services.sentence_emotion import classify_by_sentence
from app.services.text_emotion import TextEmotionClassifier

KEYWORD_COUNT = 4
# KOTE 6종 묶음의 기본 문턱값(KOTE_THRESHOLD)과 같은 값 — 이보다 약한 라벨은 키워드로 내지 않는다.
KEYWORD_MIN_SCORE = 0.4

# KOTE 라벨은 "화남/분노"처럼 비슷한 말을 묶어 둔 이름이라 앞말만 보여준다.
# 앞말이 화면에 어색한 라벨만 따로 고른다.
_KEYWORD_NAMES = {
    "환영/호의": "호의",
    "패배/자기혐오": "자기혐오",
    "부담/안_내킴": "부담",
}


@dataclass
class AnswerEmotion:
    scores: dict[str, float]  # 6종 상대 점수(합 1), 판단 불가면 모두 0
    dominant_emotion: str | None
    confidence: float
    keywords: list[str]  # KOTE 세부 감정, 점수 높은 순. 판단 불가면 빈 목록


def keyword_name(label: str) -> str:
    if label in _KEYWORD_NAMES:
        return _KEYWORD_NAMES[label]
    return label.split("/")[0].split("(")[0].replace("_", " ").strip()


def emotion_keywords(labels: dict[str, float]) -> list[str]:
    ranked = sorted(
        (label for label, value in labels.items() if label != "없음" and value >= KEYWORD_MIN_SCORE),
        key=labels.get,
        reverse=True,
    )
    return [keyword_name(label) for label in ranked[:KEYWORD_COUNT]]


def analyze_answer(classifier: TextEmotionClassifier, text: str) -> AnswerEmotion:
    result = classify_by_sentence(classifier, text)
    keywords = emotion_keywords(result.labels) if result.dominant_emotion else []
    return AnswerEmotion(
        scores=result.scores,
        dominant_emotion=result.dominant_emotion,
        confidence=result.confidence,
        keywords=keywords,
    )
