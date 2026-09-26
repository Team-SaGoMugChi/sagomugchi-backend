"""텍스트(KOTE) 감정 + 표정 감정 근거 + 음성 흥분도 → 최종 감정 (멀티모달 융합).

fusion.py(텍스트 점수를 그대로 쓰고 표정·음성은 변화 크기만 강도에 섞는 잠정 구현)를
대체하기 위한 규칙이다. API 연결 전까지 fusion.py는 그대로 둔다.

규칙
    최종 점수 = 텍스트 점수 × 보정값, 합이 1이 되게 다시 나눈다.
    보정값 = 1 + W_FACE × 표정의 그 감정 근거
               + W_VALENCE × 표정 긍정도 × 감정 방향(기쁨 +1, 부정 감정 −1, 당황 0)
               + W_AROUSAL × 음성 흥분도 × 감정 흥분도(분노·불안·당황·기쁨 +1, 슬픔·상처 −1)
    감정 흥분도는 러셀의 감정 원형 모델(긍정도 × 각성도) 배치를 따른다.

텍스트가 중심이다: 텍스트가 0인 감정은 표정·음성이 아무리 강해도 새로 생기지 않고,
텍스트가 고른 후보들 사이의 순위만 바뀐다. 텍스트가 판단 불가면 결과도 판단 불가다 —
얼굴·목소리만으로 감정을 단정하면 오판 위험이 크다.

불일치(incongruent)는 논문 3.2.3의 "모달리티 간 부조화 감지"다("괜찮다고 말하지만 음성 Δ와
표정 Δ가 부정 방향으로 큰 경우"). 두 가지로 판단하고, 어디서 걸렸는지 incongruence_sources에 남긴다.
    표정: 텍스트 긍정도와 표정 긍정도가 반대 방향으로 뚜렷할 때.
    음성: 말은 긍정인데 목소리가 뚜렷하게 가라앉았을 때(흥분도 ≤ −0.4). 흥분도만으로는 긍정·부정을
          알 수 없어서, 표정이 뚜렷하게 밝으면(긍정도 ≥ +0.2) 켜지 않는다. 웹캠 실험에서 괜찮은 척
          녹음은 두 번 모두 흥분도 −0.6(목소리 높이·크기 하락), 진짜 기쁨 녹음은 −0.05였다.
          "편안하게 쉬었다"처럼 차분한 긍정은 잘못 걸릴 수 있다 — 평가셋으로 확인할 것.
부정적인 말에 높은 흥분도는 분노·불안에서 자연스러우므로 음성 불일치로 보지 않는다.

가중치·문턱값은 학습된 값이 아니라 이론 기반 잠정 규칙이다. 오또 일기로 만든 평가셋으로
검증·조정해야 한다.
"""

from dataclasses import dataclass, field

from app.services.modality_emotion import FaceEmotion, VoiceArousal, describe_signals
from app.services.text_emotion import EMOTION_LABELS, TextEmotionResult

W_FACE = 1.0
W_VALENCE = 0.5
W_AROUSAL = 0.5
# 보정값이 0 이하가 되거나 한 모달리티가 텍스트를 압도하지 않게 자른다.
MIN_MULTIPLIER = 0.25
MAX_MULTIPLIER = 3.0

VALENCE_SIGN = {"기쁨": 1, "슬픔": -1, "분노": -1, "불안": -1, "상처": -1, "당황": 0}
AROUSAL_SIGN = {"기쁨": 1, "슬픔": -1, "분노": 1, "불안": 1, "상처": -1, "당황": 1}

# 강도 = 텍스트 확신도와 표정·음성 변화 크기의 가중 평균.
INTENSITY_TEXT_WEIGHT = 0.6
INCONGRUENCE_THRESHOLD = 0.3
VOICE_INCONGRUENCE_AROUSAL = -0.4
FACE_CLEARLY_POSITIVE = 0.2
TOP_KEYWORD_COUNT = 2


@dataclass
class MultimodalResult:
    emotion_keywords: list[str]  # 점수 상위 감정 (판단 불가면 빈 목록)
    emotion_scores: dict[str, float]  # 6종, 0~100
    emotion_intensity: int  # 0~100
    text_emotion: TextEmotionResult
    face: FaceEmotion | None
    voice: VoiceArousal | None
    signals: list[str] = field(default_factory=list)  # 상담봇 맥락용 변화 문장
    incongruent: bool = False  # 말과 표정·목소리가 어긋남 → 상담봇 역질문 트리거
    incongruence_sources: list[str] = field(default_factory=list)  # 어긋난 쪽 ("face", "voice")
    modalities: list[str] = field(default_factory=list)  # 실제로 반영된 입력 ("text", "face", "voice")


def text_valence(scores: dict[str, float]) -> float:
    """텍스트 6종 점수의 긍정도 −1~1."""
    return sum(scores.get(label, 0.0) * sign for label, sign in VALENCE_SIGN.items())


def incongruence_sources(spoken: float, face: FaceEmotion | None, voice: VoiceArousal | None) -> list[str]:
    """텍스트 긍정도 spoken과 어긋나는 모달리티 목록."""
    sources = []
    if face is not None and (
        (spoken >= INCONGRUENCE_THRESHOLD and face.valence <= -INCONGRUENCE_THRESHOLD)
        or (spoken <= -INCONGRUENCE_THRESHOLD and face.valence >= INCONGRUENCE_THRESHOLD)
    ):
        sources.append("face")
    if (
        voice is not None
        and spoken >= INCONGRUENCE_THRESHOLD
        and voice.arousal <= VOICE_INCONGRUENCE_AROUSAL
        and (face is None or face.valence < FACE_CLEARLY_POSITIVE)
    ):
        sources.append("voice")
    return sources


def _multiplier(label: str, face: FaceEmotion | None, voice: VoiceArousal | None) -> float:
    value = 1.0
    if face is not None:
        value += W_FACE * face.scores.get(label, 0.0)
        value += W_VALENCE * face.valence * VALENCE_SIGN[label]
    if voice is not None:
        value += W_AROUSAL * voice.arousal * AROUSAL_SIGN[label]
    return min(max(value, MIN_MULTIPLIER), MAX_MULTIPLIER)


def _intensity(text: TextEmotionResult, face: FaceEmotion | None, voice: VoiceArousal | None) -> int:
    changes = []
    if face is not None:
        changes.append(max(face.scores.values(), default=0.0))
    if voice is not None:
        changes.append(abs(voice.arousal))
    if changes:
        value = INTENSITY_TEXT_WEIGHT * text.confidence + (1 - INTENSITY_TEXT_WEIGHT) * sum(changes) / len(changes)
    else:
        value = text.confidence
    return max(0, min(100, round(value * 100)))


def fuse_multimodal(
    text: TextEmotionResult,
    face: FaceEmotion | None = None,
    voice: VoiceArousal | None = None,
    signal_limit: int = 4,
) -> MultimodalResult:
    signals = describe_signals(face.z if face else None, voice.z if voice else None, limit=signal_limit)
    modalities = ["text"] + (["face"] if face else []) + (["voice"] if voice else [])

    if text.dominant_emotion is None:
        return MultimodalResult(
            emotion_keywords=[],
            emotion_scores=dict.fromkeys(EMOTION_LABELS, 0.0),
            emotion_intensity=0,
            text_emotion=text,
            face=face,
            voice=voice,
            signals=signals,
            incongruent=False,
            modalities=modalities,
        )

    raw = {label: text.scores.get(label, 0.0) * _multiplier(label, face, voice) for label in EMOTION_LABELS}
    total = sum(raw.values())
    fused = {label: value / total for label, value in raw.items()} if total > 0 else dict(text.scores)

    scores = {label: round(fused[label] * 100, 1) for label in EMOTION_LABELS}
    keywords = [label for label in sorted(scores, key=scores.get, reverse=True) if scores[label] > 0][
        :TOP_KEYWORD_COUNT
    ]

    sources = incongruence_sources(text_valence(text.scores), face, voice)

    return MultimodalResult(
        emotion_keywords=keywords,
        emotion_scores=scores,
        emotion_intensity=_intensity(text, face, voice),
        text_emotion=text,
        face=face,
        voice=voice,
        signals=signals,
        incongruent=bool(sources),
        incongruence_sources=sources,
        modalities=modalities,
    )
