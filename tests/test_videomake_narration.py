"""나레이션 말투(해요체)와 인지왜곡 기준. LLM은 가짜라 비용 0."""

from app.videomake.guardrails import lint_name_repetition, lint_narration
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.stages.storyboard import _StoryboardDraft


def _rules(violations):
    return [v.rule for v in violations]


def test_haeyo_endings_pass():
    for text in ["민준은 도시락을 열고 웃었어요.", "오후엔 조금 지쳤어요", "집에 가는 길이 신났어요!"]:
        assert "해요체로 쓴다" not in _rules(lint_narration(text, "민준", 8))


def test_literary_endings_are_fed_back():
    violations = lint_narration("확인은 부담처럼 보였다", "민준", 8)
    assert "해요체로 쓴다" in _rules(violations)
    assert "~했어요" in violations[0].detail


def _system():
    p = get_prompts()
    return p.render(
        "storyboard_planner.system.md",
        min_cuts=3, max_cuts=10, min_total_seconds=12, max_total_seconds=40,
        cut_durations=(4, 6, 8), narration_limits={4: 14, 6: 21, 8: 28}, dialogue_limits={},
        dialogue_min_seconds=6, distancing_rules=p.distancing_rules,
        protagonist_hint="주인공", dialogue_max_lines=3, dialogue_min_lines=2,
    )


def test_planner_writes_warm_narration_not_a_therapy_case():
    system = _system()

    assert "심리치료 목적" not in system
    assert "해요체로 쓴다" in system
    assert "관찰하고 기술한다" not in system
    assert "일기에 없는 문제를 찾아내거나" in system


def test_distortions_only_when_clearly_written():
    system = _system()

    assert "분명히 적혀 있을 때만" in system
    assert "찾으려고 애쓰지 않는다" in system
    assert '"너무 피곤했다"는 왜곡이 아니라 사실이다' in system


def _storyboard(narrations):
    payload = fake.demo_storyboard_payload(len(narrations))
    for cut, text in zip(payload["cuts"], narrations):
        cut["narration"] = text
    return _StoryboardDraft.model_validate(payload).to_storyboard()


def test_name_in_every_narration_is_fed_back():
    sb = _storyboard([f"지훈은 {t}" for t in ["도착했어요.", "책을 폈어요.", "웃었어요.", "지쳤어요.", "걸었어요.", "웃었어요."]])

    violations = lint_name_repetition(sb)

    assert len(violations) == 1
    assert "나레이션 6개 중 6개(컷 1·2·3·4·5·6)" in violations[0].detail
    assert "2번 이하로 줄이고" in violations[0].detail


def test_name_a_few_times_is_fine():
    sb = _storyboard(["지훈은 도착했어요.", "책을 폈어요.", "도시락에 웃었어요.", "지훈은 집에 갔어요."])
    assert lint_name_repetition(sb) == []


def test_planner_is_told_to_drop_the_subject():
    assert "주어를 생략한다" in _system()


def test_eating_may_mention_the_mouth_but_speaking_motion_may_not():
    from app.videomake.guardrails import lint_motion_prompt

    def mouth_rules(text):
        return [v.rule for v in lint_motion_prompt(text) if "입" in v.rule]

    assert mouth_rules("He lifts a spoonful of rice to his mouth and smiles.") == []
    assert mouth_rules("He wipes his mouth with a napkin.") == []
    assert mouth_rules("He opens his mouth as if to answer.") == ["입 움직임 연출 금지 (원칙 7)"]
    assert mouth_rules("Her mouth moves slightly.") == ["입 움직임 연출 금지 (원칙 7)"]
