"""상담 할루시네이션 방지 — 사실 근거·지어낸 기억 차단·리포트 근거 확인."""

import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services import counsel_report
from app.services.counsel_prompt import build_system_prompt

client = TestClient(app)

_SLOTS = {
    "무엇을": "팀 회의에서 낸 의견이 그냥 넘어감",
    "누가": "팀장님과 팀원 4명",
    "그때 기분": "무시당한 것 같아서 서운했어",
    "지금 기분": "아직 좀 가라앉아 있어",
}


# ── 프롬프트 ─────────────────────────────────────────────────────────

def test_prompt_has_no_past_session_example_without_recent_themes():
    prompt = build_system_prompt()
    # 지난 상담이 없는데 "지난번에도"를 흉내 낼 예시가 들어가면 기억을 지어낸다.
    assert "지난번에도" not in prompt
    assert "지난 상담에서도" not in prompt
    assert "[지난 상담 주제]" in prompt  # 원칙 설명에서 이름만 언급된다
    assert "최근 상담에서 반복된 주제:" not in prompt


def test_prompt_mentions_past_theme_only_when_given():
    prompt = build_system_prompt(recent_themes=["자기 비난"])
    assert "최근 상담에서 반복된 주제: 자기 비난" in prompt
    assert "지어내지 않는다" in prompt


def test_prompt_includes_user_stated_facts_in_order():
    prompt = build_system_prompt(slots=_SLOTS)
    assert "[오늘 일기 사실 — 사용자가 직접 말한 내용]" in prompt
    assert "- 무슨 일: 팀 회의에서 낸 의견이 그냥 넘어감" in prompt
    assert "- 함께한 사람: 팀장님과 팀원 4명" in prompt
    # 정해진 순서(무엇을 → 누가 → 그때 기분 → 지금 기분)
    assert prompt.index("무슨 일:") < prompt.index("함께한 사람:") < prompt.index("지금 기분:")


def test_prompt_skips_fact_section_when_no_slots():
    assert "[오늘 일기 사실 — 사용자가 직접 말한 내용]" not in build_system_prompt(slots={})


def test_prompt_includes_emotion_arc():
    prompt = build_system_prompt(emotion_arc="불안 → 상처 → 안도")
    assert "일기 속 감정 흐름: 불안 → 상처 → 안도" in prompt


def test_prompt_has_grounding_rules():
    prompt = build_system_prompt()
    assert "[사실에 근거하기" in prompt
    assert "연구 결과·통계·수치를 인용하지 않는다" in prompt


# ── API ──────────────────────────────────────────────────────────────

def test_counsel_turn_passes_slots_and_arc_to_prompt(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()
    captured = {}

    def chat(system_prompt, messages):
        captured["system_prompt"] = system_prompt
        return "의견이 그냥 넘어가서 서운하셨군요."

    monkeypatch.setattr("app.api.routes.counsel.llm_client.chat", chat)
    response = client.post(
        "/counsel/turn",
        json={
            "user_text": "아까 회의 생각이 계속 나",
            "slots": {**_SLOTS, "어디서": None, "왜": "  "},
            "emotion_arc": "서운함 → 가라앉음",
        },
    )

    assert response.status_code == 200
    prompt = captured["system_prompt"]
    assert "팀 회의에서 낸 의견이 그냥 넘어감" in prompt
    assert "서운함 → 가라앉음" in prompt
    assert "- 어디서:" not in prompt  # 빈 칸은 넣지 않는다
    assert "- 사용자가 생각하는 이유:" not in prompt


def test_counsel_turn_rejects_too_many_slots():
    response = client.post(
        "/counsel/turn",
        json={"user_text": "안녕", "slots": {f"k{i}": "v" for i in range(13)}},
    )
    assert response.status_code == 422


# ── 리포트 근거 확인 ─────────────────────────────────────────────────

_MESSAGES = [
    {"role": "user", "content": "오늘 팀 회의에서 낸 의견이 그냥 넘어갔어"},
    {"role": "assistant", "content": "그때 어떤 생각이 스쳤어요?"},
    {"role": "user", "content": "내 의견은 늘 별로라고 생각했어"},
    {"role": "assistant", "content": "그 생각을 뒷받침하는 일과 아닌 일이 있을까요?"},
    {"role": "user", "content": "지난주엔 내 아이디어가 채택됐었지. 늘 그런 건 아니네"},
]


def _fake_llm(payload: dict):
    def chat(system_prompt, messages, **kwargs):
        chat.kwargs = kwargs
        return json.dumps(payload, ensure_ascii=False)

    return chat


def test_report_drops_moments_not_grounded_in_user_words(monkeypatch):
    fake = _fake_llm(
        {
            "headline": "의견이 넘어간 날",
            "summary": "회의에서 의견이 넘어가 서운했어요.",
            "moments": [
                "지난주에 아이디어가 채택된 적도 있다는 걸 떠올렸어요.",  # 근거 있음
                "어릴 때부터 인정받지 못했던 경험이 떠올랐어요.",  # 지어낸 내용
            ],
            "reframe": "의견이 채택되지 않은 날이 있다고 해서 늘 그런 건 아닐 수 있어요.",
            "suggestion": "",
            "closing": "오늘은 여기까지도 충분해요.",
        }
    )
    monkeypatch.setattr(counsel_report.llm_client, "chat", fake)

    report = counsel_report.build(_MESSAGES)

    assert report["moments"] == ["지난주에 아이디어가 채택된 적도 있다는 걸 떠올렸어요."]
    assert report["reframe"]  # 사용자 말과 겹쳐서 남는다
    # 리포트는 JSON 모드·낮은 temperature로 생성한다
    assert fake.kwargs["json_mode"] is True
    assert fake.kwargs["temperature"] <= 0.3


def test_report_drops_reframe_without_any_grounding(monkeypatch):
    monkeypatch.setattr(
        counsel_report.llm_client,
        "chat",
        _fake_llm(
            {
                "headline": "의견이 넘어간 날",
                "summary": "회의에서 서운했어요.",
                "moments": [],
                "reframe": "부모님과의 관계에서 비롯된 패턴일 수도 있어요.",
                "suggestion": "",
                "closing": "수고했어요.",
            }
        ),
    )

    assert counsel_report.build(_MESSAGES)["reframe"] == ""


def test_report_accepts_slots_as_grounding(monkeypatch):
    monkeypatch.setattr(
        counsel_report.llm_client,
        "chat",
        _fake_llm(
            {
                "headline": "서운했던 회의",
                "summary": "회의에서 서운했어요.",
                "moments": ["팀장님과 팀원들 앞이라 더 서운했다는 걸 알아차렸어요."],
                "reframe": "",
                "suggestion": "",
                "closing": "수고했어요.",
            }
        ),
    )

    report = counsel_report.build(_MESSAGES, slots=_SLOTS)

    assert report["moments"] == ["팀장님과 팀원들 앞이라 더 서운했다는 걸 알아차렸어요."]


def test_report_skips_llm_for_single_turn(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(counsel_report.llm_client, "chat", fail)
    report = counsel_report.build([{"role": "user", "content": "그냥 피곤해"}])
    assert report["moments"] == []