"""Six-emotion contract. Production uses KOTE; keywords remain test-only.

ALBERT / AI Hub checkpoints are not loaded. See docs/KOTE.md.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

EMOTION_LABELS = ["기쁨", "슬픔", "분노", "불안", "상처", "당황"]


@dataclass
class TextEmotionResult:
    scores: dict[str, float]  # 6종 상대 점수; 합 1, 판단 불가 시 모두 0 (KOTE)
    dominant_emotion: str | None  # 근거가 부족하면 None(판단 불가)
    confidence: float  # 근거 점수, 보정된 정확도/감정 강도가 아님


class TextEmotionClassifier(ABC):
    @abstractmethod
    def classify(self, text: str) -> TextEmotionResult: ...


class KeywordTextEmotionClassifier(TextEmotionClassifier):
    """모델 없이 동작하는 임시 폴백. 키워드 등장 횟수로 점수화한다."""

    _KEYWORDS: dict[str, list[str]] = {
        # "좋"은 "좋지 않아"/"안 좋아" 같은 부정문에도 걸려 기쁨 오탐이 심해서 제외 —
        # AI Hub 감성대화 말뭉치로 검증한 결과 이 항목 때문에 다른 라벨의 60~75%가 기쁨으로 오분류됨.
        "기쁨": ["행복", "기쁘", "즐겁", "웃", "신나", "설레"],
        "슬픔": ["슬프", "우울", "눈물", "속상", "그립"],
        "분노": ["화나", "짜증", "열받", "억울", "분하", "화가"],
        "불안": ["불안", "걱정", "긴장", "무섭", "두렵"],
        "상처": ["상처", "서운", "실망", "배신", "아프"],
        "당황": ["당황", "황당", "어이없", "놀라", "혼란"],
    }

    def classify(self, text: str) -> TextEmotionResult:
        counts = {label: sum(text.count(kw) for kw in keywords) for label, keywords in self._KEYWORDS.items()}
        total = sum(counts.values())

        if total == 0:
            # 매칭 키워드가 없으면 균등분포(중립)로 취급 — dominant_emotion은 특정 라벨로 단정하지 않고
            # None으로 남겨 "판단 불가"를 명시한다. (이전엔 max()의 동점 처리가 dict 첫 키인 "기쁨"을
            # 항상 골라, 매칭 실패 시 전부 기쁨으로 오분류되는 버그가 있었음 — 말뭉치 검증 시 44%가 이 경로)
            scores = {label: 1.0 / len(EMOTION_LABELS) for label in EMOTION_LABELS}
            return TextEmotionResult(scores=scores, dominant_emotion=None, confidence=scores[EMOTION_LABELS[0]])

        scores = {label: count / total for label, count in counts.items()}
        dominant_emotion = max(scores, key=scores.get)
        return TextEmotionResult(scores=scores, dominant_emotion=dominant_emotion, confidence=scores[dominant_emotion])


@lru_cache(maxsize=1)
def get_text_emotion_classifier() -> TextEmotionClassifier:
    from app.core.config import get_settings
    from app.services.kote_emotion import KoteTextEmotionClassifier

    settings = get_settings()
    return KoteTextEmotionClassifier(
        cache_dir=settings.kote_cache_dir,
        local_files_only=settings.kote_local_files_only,
        device=settings.kote_device,
        threshold=settings.kote_threshold,
    )
