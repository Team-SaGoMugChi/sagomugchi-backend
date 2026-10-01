import pytest

from app.services.counsel_guardrail import RiskLevel, assess, is_crisis


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