import pytest

from app.services.counsel_guardrail import (
    CAUTION_GUIDES,
    CRISIS_REPLIES,
    RiskAxis,
    RiskLevel,
    assess,
    caution_guide,
    crisis_reply,
    is_crisis,
)


@pytest.mark.parametrize(
    "text",
    [
        # 죽음·소멸 바람
        "그냥 다 사라지고 싶어",
        "요즘 죽고 싶다는 생각이 들어",
        "죽고싶다 ㅋㅋ",  # 웃음은 위험도를 낮추지 않는다
        "살기 싫어",
        "이제 그만 살고 싶어",
        "힘들어서 죽고 싶어",  # 마음의 고통이 이유면 낮추지 않는다
        "우울해서 죽고 싶다",
        "외로워서 죽고 싶어",
        "태어나지 말았어야 했어",
        # 방법·계획
        "인생 끝내고 싶어",
        "모든 걸 끝내고 싶어",
        "자해를 생각했어",
        "유서를 써놨어",
        "약을 모아두고 있어",
        "뛰어내리면 편할까",
        "영화 보고 나도 자해하고 싶어졌어",  # 정보 맥락이어도 본인 의도
        # 과장처럼 보이지만 진심 표시
        "배고파서 죽고 싶어 진짜로",
        "농담 아니고 죽고 싶어",
    ],
)
def test_crisis(text: str) -> None:
    result = assess(text)
    assert result.level is RiskLevel.CRISIS, result
    assert is_crisis(text)


@pytest.mark.parametrize(
    "text",
    [
        "배고파 죽고 싶어",  # 사소한 이유 + 죽고 싶 → 상담봇이 맥락으로 확인
        "졸려서 죽고 싶다",
        "죽고 싶은 건 아니야",  # 부정
        "죽고 싶진 않은데 좀 지쳐",
        "자살 예방 캠페인 뉴스 봤어",  # 정보 맥락
        "나는 자살 예방 수업 들었어",
        "영화에서 주인공이 자살했어",
        "친구가 자해한다고 해서 걱정돼",  # 제3자
        "친구가 자해했다고 들었어",
        "너 죽을래?",  # 모호
        "웃겨 죽을래",
    ],
)
def test_caution(text: str) -> None:
    result = assess(text)
    assert result.level is RiskLevel.CAUTION, result
    assert not is_crisis(text)


@pytest.mark.parametrize(
    "text",
    [
        "배고파 죽겠어",
        "배고파죽겟어",  # 오타
        "졸려 죽을 것 같아",
        "웃겨 죽는 줄 알았어",
        "더워서 죽겠다",
        "피곤해 죽겠어",
        "진짜 배고파 죽겠어",  # 강조 표현은 진심 표시가 있어도 그대로
        "공부해야지",
        "과제 빨리 끝내고 싶어",
        "이번 주 안에 프로젝트 끝내고 싶어",
        "오늘 회의에서 내 의견이 무시당했어",
        "시험 끝나고 푹 쉬고 싶어",
        "회의 내용 요약 모아서 정리했어",  # '약모아' 오탐 방지
        "유서 깊은 절에 다녀왔어",  # '유서' 오탐 방지
        "",
    ],
)
def test_none(text: str) -> None:
    assert assess(text).level is RiskLevel.NONE


# ── 자살 축 — 간접 표현 (PR3 평가에서 놓친 말) ──────────────────────────
@pytest.mark.parametrize(
    "text",
    [
        "요즘은 그냥 아침에 눈 안 떴으면 좋겠어",
        "다 포기하고 싶어 그냥 끝내버리고 싶다",
        "내가 죽으면 누가 슬퍼할까",
        "살아있는 게 의미가 없어",
        "한강 가고 싶다는 생각이 들어",
        "그냥 영원히 잠들고 싶다",
        "살 이유를 모르겠어",
    ],
)
def test_indirect_ideation_is_crisis(text: str) -> None:
    result = assess(text)
    assert result.level is RiskLevel.CRISIS, result
    assert result.axis is RiskAxis.SUICIDE


@pytest.mark.parametrize(
    "text",
    [
        "친구가 요즘 죽고 싶다고 해서 걱정돼",  # 남의 말 전달
        "죽고 싶다까지는 아닌데 힘들어",  # 부정
        "옛날에 죽고 싶었던 적 있는데 지금은 괜찮아",  # 과거
    ],
)
def test_softened_desire_is_caution(text: str) -> None:
    assert assess(text).level is RiskLevel.CAUTION


def test_own_thought_with_family_word_stays_crisis() -> None:
    # 가족이 나와도 "~다고 느꼈어"는 본인 마음이라 낮추지 않는다.
    assert assess("엄마가 화내서 죽고 싶다고 느꼈어").level is RiskLevel.CRISIS


@pytest.mark.parametrize(
    "text",
    ["과제 끝내버리고 싶어", "이번 프로젝트 그냥 끝내버리고 싶어", "한강 뷰 카페 가고 싶어"],
)
def test_task_or_place_words_are_not_crisis(text: str) -> None:
    assert assess(text).level is RiskLevel.NONE


# ── 다른 축 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text, level, axis",
    [
        ("지금 남편이 때리고 있어", RiskLevel.CRISIS, RiskAxis.DANGER),
        ("누가 집 앞까지 따라왔어 무서워", RiskLevel.CRISIS, RiskAxis.DANGER),
        ("전 남친이 스토킹해서 무서워", RiskLevel.CAUTION, RiskAxis.DANGER),
        ("칼 들고 걔 찾아갈 거야", RiskLevel.CRISIS, RiskAxis.HARM_OTHERS),
        ("팀장 진짜 죽이고 싶다", RiskLevel.CAUTION, RiskAxis.HARM_OTHERS),
        ("목소리가 자꾸 죽으라고 해", RiskLevel.CRISIS, RiskAxis.PSYCHOSIS),
        ("누가 계속 나를 감시하는 것 같아", RiskLevel.CAUTION, RiskAxis.PSYCHOSIS),
        ("너밖에 없어 사람들은 다 싫어", RiskLevel.CAUTION, RiskAxis.DEPENDENCE),
    ],
)
def test_other_axes(text: str, level: RiskLevel, axis: RiskAxis) -> None:
    result = assess(text)
    assert (result.level, result.axis) == (level, axis), result


def test_suicide_method_wins_over_psychosis() -> None:
    # 명령 환청이 자살 방법을 담으면 자살 축 안내(109)가 우선이다.
    result = assess("목소리가 창문으로 뛰어내리라고 해")
    assert (result.level, result.axis) == (RiskLevel.CRISIS, RiskAxis.SUICIDE)


@pytest.mark.parametrize(
    "text",
    [
        "칼 들고 양파 썰었어",
        "감기약을 다 먹었어",
        "강아지가 집까지 따라왔어",
        "친구한테 맞춰주느라 피곤했어",
        "목소리가 작다고 크게 말하라고 하셨어",
    ],
)
def test_everyday_words_on_other_axes_are_none(text: str) -> None:
    assert assess(text).level is RiskLevel.NONE


def test_every_crisis_axis_has_reply_with_hotline() -> None:
    hotlines = {
        RiskAxis.SUICIDE: "109",
        RiskAxis.DANGER: "112",
        RiskAxis.HARM_OTHERS: "1577-0199",
        RiskAxis.PSYCHOSIS: "1577-0199",
    }
    for axis, number in hotlines.items():
        assert number in CRISIS_REPLIES[axis]
    assert "112" in crisis_reply(assess("지금 아빠가 때리고 있어"))


def test_every_axis_has_caution_guide() -> None:
    assert set(CAUTION_GUIDES) == set(RiskAxis)
    assert "오또" in caution_guide(assess("너랑 사귀고 싶어"))