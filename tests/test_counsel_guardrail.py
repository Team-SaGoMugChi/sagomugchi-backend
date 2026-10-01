import pytest

from app.services.counsel_guardrail import is_crisis


@pytest.mark.parametrize(
    "text",
    [
        "그냥 다 사라지고 싶어",
        "요즘 죽고 싶다는 생각이 들어",
        "살기 싫어",
        "이제 그만 살고 싶어",
        "인생 끝내고 싶어",
        "모든 걸 끝내고 싶어",
        "자해를 생각했어",
        "배고파 죽고 싶어",  # 과장 표현도 안전을 위해 위기로 본다
    ],
)
def test_crisis_detected(text: str) -> None:
    assert is_crisis(text)


@pytest.mark.parametrize(
    "text",
    [
        "과제 빨리 끝내고 싶어",
        "이번 주 안에 프로젝트 끝내고 싶어",
        "오늘 회의에서 내 의견이 무시당했어",
        "시험 끝나고 푹 쉬고 싶어",
        "빨리 퇴근하고 싶다",
    ],
)
def test_everyday_phrases_not_crisis(text: str) -> None:
    assert not is_crisis(text)