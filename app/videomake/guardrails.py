"""연출 원칙을 코드로 강제하는 린터.

스토리보드 생성 직후에 돌린다. LLM 호출은 영상 1컷의 1/100 비용이므로
여기서 반복해서 고치는 것은 사실상 공짜다. 영상 단계까지 위반을 흘려보내면
컷당 $0.80을 버리게 된다.
"""

from __future__ import annotations

import re

from .config import NARRATION_MAX_CHARS
from .models import Cut, Storyboard, Violation

# --- image_prompt 금지 ------------------------------------------------------
_POV_PATTERNS = [
    (r"\bpov\b", "POV 샷 금지 (원칙 1)"),
    (r"first[- ]person", "1인칭 시점 금지 (원칙 1)"),
    (r"\bselfie\b", "셀피 구도는 1인칭이다 (원칙 1)"),
    (r"through (his|her|their) eyes", "시점 샷 금지 (원칙 1)"),
    (r"looking (down )?at (his|her|their) own", "자기 신체 시점 금지 (원칙 1)"),
]
# 카메라를 사람 뒤에 두는 구도. "over-the-shoulder"라고 쓰지 않아도
# "past the silhouettes of colleagues in the foreground" 식으로 우회한다.
# 관찰자가 무리 안으로 들어가 버려서 거리가 무너진다.
_OVER_SHOULDER_PATTERNS = [
    (r"over[- ]the[- ]shoulder|over[- ]shoulder", "오버숄더 구도 금지 (원칙 1·2)"),
    (
        (
            r"(past|behind|between|through)\s+(the\s+)?[\w\s,-]{0,40}?"
            r"(silhouettes?|figures?|shoulders?|heads?|colleagues?|bodies)"
        ),
        "인물 뒤에서 넘겨보는 구도 금지 (원칙 1·2)",
    ),
    (
        (
            r"foreground[\w\s,-]{0,20}?"
            r"(silhouettes?|figures?|shoulders?|heads?|colleagues?|onlookers?)"
        ),
        "전경에 인물을 두면 관찰 거리가 무너진다 (원칙 2)",
    ),
    (
        (
            r"(framed|obscured|partially hidden) by[\w\s,-]{0,25}?"
            r"(silhouettes?|figures?|colleagues?|people)"
        ),
        "인물로 프레이밍하지 않는다 (원칙 2)",
    ),
]
_CLOSEUP_PATTERNS = [
    (r"extreme close[- ]?up", "익스트림 클로즈업 금지 (원칙 2)"),
    (r"\bmacro\b", "매크로 샷은 거리 원칙 위반 (원칙 2)"),
    (r"face fill(s|ing) the frame", "얼굴이 화면을 채우면 안 된다 (원칙 2)"),
    (r"tight (shot|framing) on (his|her|their) face", "얼굴 타이트 샷 금지 (원칙 2)"),
]
_EXAGGERATION_PATTERNS = [
    (r"\bscream(ing|s)?\b", "절규 연출 금지 (원칙 5)"),
    (r"\bsobbing\b", "오열 연출 금지 (원칙 5)"),
    (r"\bwailing\b", "통곡 연출 금지 (원칙 5)"),
    (r"\bterror\b|\bhorrified\b", "공포 과장 금지 (원칙 5)"),
    (r"exaggerated", "과장된 표현 금지 (원칙 5)"),
]
# --- motion_prompt 금지 -----------------------------------------------------
_SPEECH_PATTERNS = [
    (r"\bsay(s|ing)?\b|\bspeak(s|ing)?\b|\btalk(s|ing)?\b", "발화 연출 금지 (원칙 7)"),
    (r"\blips?\b", "입 움직임 연출 금지 (원칙 7)"),
    (r"\bdialogue\b|\bshout(s|ing)?\b", "대사 금지 (원칙 7)"),
    (r"\bmouths?\b", "입 묘사 금지 (원칙 7)"),
]
_FAST_CAMERA_PATTERNS = [
    (r"quick(ly)? (pan|zoom|cut)", "급격한 카메라 이동 금지 (원칙 2)"),
    (r"\bzoom(s|ing)? in\b", "줌 인은 관찰 거리를 무너뜨린다 (원칙 2)"),
    (r"rapid|sudden(ly)?|abrupt", "급격한 변화 금지 (관찰자 톤)"),
    (r"cuts? to\b", "컷 전환 금지 — 한 컷은 하나의 연속 샷이다"),
]

# 나레이션 1인칭 (원칙 3)
_FIRST_PERSON_KO = ["나는 ", "내가 ", "나를 ", "나의 ", "우리는 ", "우리가 ", "저는 "]

# motion_prompt가 장면을 다시 묘사하면 모델이 첫 프레임을 재해석한다.
MOTION_MAX_WORDS = 45


def _scan(text: str, patterns: list[tuple[str, str]], field: str) -> list[Violation]:
    lowered = text.lower()
    out: list[Violation] = []
    for pattern, rule in patterns:
        m = re.search(pattern, lowered)
        if m:
            out.append(Violation(field=field, rule=rule, detail=f'"{m.group(0)}" 발견'))
    return out


def lint_image_prompt(prompt: str) -> list[Violation]:
    return (
        _scan(prompt, _POV_PATTERNS, "image_prompt")
        + _scan(prompt, _OVER_SHOULDER_PATTERNS, "image_prompt")
        + _scan(prompt, _CLOSEUP_PATTERNS, "image_prompt")
        + _scan(prompt, _EXAGGERATION_PATTERNS, "image_prompt")
    )


def lint_motion_prompt(prompt: str) -> list[Violation]:
    out = _scan(prompt, _SPEECH_PATTERNS, "motion_prompt")
    out += _scan(prompt, _FAST_CAMERA_PATTERNS, "motion_prompt")
    words = len(prompt.split())
    if words > MOTION_MAX_WORDS:
        out.append(
            Violation(
                field="motion_prompt",
                rule="motion_prompt는 변화만 쓴다",
                detail=(
                    f"{words}단어로 {MOTION_MAX_WORDS}단어 상한 초과. "
                    "장면을 다시 묘사하고 있을 가능성이 높다."
                ),
            )
        )
    return out


def lint_narration(text: str, protagonist: str) -> list[Violation]:
    out: list[Violation] = []
    if len(text) > NARRATION_MAX_CHARS:
        out.append(
            Violation(
                field="narration",
                rule=f"나레이션 {NARRATION_MAX_CHARS}자 이내",
                detail=f"{len(text)}자. 컷 길이 안에 읽히지 않는다.",
            )
        )
    padded = f" {text} "
    for token in _FIRST_PERSON_KO:
        if token in padded:
            out.append(
                Violation(
                    field="narration",
                    rule="1인칭 금지 (원칙 3)",
                    detail=f'"{token.strip()}" 사용. 3인칭 또는 "{protagonist}"로 바꿔야 한다.',
                )
            )
    return out


def lint_cut(cut: Cut, protagonist: str) -> list[Violation]:
    out = lint_image_prompt(cut.image_prompt)
    out += lint_motion_prompt(cut.motion_prompt)
    # 1인칭 금지(원칙 3)는 화면 밖 나레이션에만 적용한다. 인물이 대사에서
    # "나"라고 말하는 것은 자연스러운 발화이지 관찰 거리의 붕괴가 아니다.
    if cut.narration is not None:
        out += lint_narration(cut.narration, protagonist)
    return [v.model_copy(update={"field": f"cut{cut.index}.{v.field}"}) for v in out]


_HANGUL = re.compile(r"[\uac00-\ud7a3]+")


def lint_english(text: str, field: str, names: set[str]) -> list[Violation]:
    """이미지·영상 모델에 그대로 들어가는 필드는 영어여야 한다.

    인물 이름은 한글 그대로 쓰는 것이 관례라 허용한다(예: "민우 sits alone").
    그 밖의 한글이 섞이면 위반이다. gpt-4o-mini는 "영어로 작성" 지시를 자주
    무시하고 한국어 프롬프트를 낸다(실제로 관측됨).
    """
    words = [w for w in _HANGUL.findall(text) if w not in names]
    if not words:
        return []
    sample = ", ".join(dict.fromkeys(words[:5]))
    return [Violation(field=field, rule="영어로 작성", detail=f"한국어 발견: {sample}")]


def lint_storyboard(sb: Storyboard) -> list[Violation]:
    out: list[Violation] = []
    names = {c.name for c in sb.characters}
    for c in sb.characters:
        out += lint_english(c.appearance, f"{c.name}.appearance", names)
        out += lint_english(c.voice, f"{c.name}.voice", names)
    for cut in sb.cuts:
        out += lint_cut(cut, sb.protagonist.name)
        out += lint_english(cut.image_prompt, f"cut{cut.index}.image_prompt", names)
        out += lint_english(cut.motion_prompt, f"cut{cut.index}.motion_prompt", names)
    # 마지막 컷은 관찰 거리를 한 번 더 넓힌다.
    if sb.cuts and sb.cuts[-1].camera_distance != "wide":
        out.append(
            Violation(
                field=f"cut{sb.cuts[-1].index}.camera_distance",
                rule="마지막 컷은 wide로 끝낸다",
                detail=f"현재 {sb.cuts[-1].camera_distance}",
            )
        )
    return out
