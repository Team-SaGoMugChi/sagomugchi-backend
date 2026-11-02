"""나레이션 다듬기 — 규칙을 어긴 결과는 쓰지 않고, 이어지는 줄은 컷 사이를 짧게 넘긴다. LLM은 가짜."""

import asyncio
import wave

from app.videomake.config import Settings
from app.videomake.models import DiaryInput, Storyboard
from app.videomake.providers import fake
from app.videomake.providers.base import LLMResult
from app.videomake.stages.compose import edit_lengths
from app.videomake.stages.narration_flow import polish_narration


class _LLM:
    def __init__(self, *scripts):
        self.scripts = list(scripts)
        self.users = []

    async def complete_json(self, *, system, user, schema):
        self.users.append(user)
        out = schema.model_validate(self.scripts.pop(0))
        return out, LLMResult(raw_json=out.model_dump_json())


def _sb() -> Storyboard:
    payload = fake.demo_storyboard_payload(3)
    for cut, text in zip(payload["cuts"], ["민지는 늦게 나왔어요.", "지하철에서 문자했어요.", "결국 웃었어요."]):
        cut.update(narration=text, dialogue=[], duration_seconds=6)
    return Storyboard.model_validate(payload)


def _script(sb, *lines):
    return {"lines": [{"cut": c.index, "narration": t} for c, t in zip(sb.cuts, lines)]}


def _diary():
    return DiaryInput(text="늦었지만 웃었다.", emotion={"primary": "기쁨"})


def test_polish_applies_valid_script():
    sb = _sb()
    llm = _LLM(_script(sb, "민지는 늦게 나왔는데,", "지하철에서 문자를 보냈어요.", "그래도 결국 웃었어요."), {"issues": []})
    out = asyncio.run(polish_narration(sb, _diary(), llm=llm))
    assert [c.narration for c in out.cuts] == ["민지는 늦게 나왔는데,", "지하철에서 문자를 보냈어요.", "그래도 결국 웃었어요."]


def test_polish_retries_with_problem_then_keeps_original():
    sb = _sb()
    bad = _script(sb, "오늘은 늦었는데,", "문자를 보냈는데,", "웃었어요,")
    llm = _LLM(bad, bad, bad, bad)
    out = asyncio.run(polish_narration(sb, _diary(), llm=llm))
    assert out == sb
    assert "직전 결과의 문제" in llm.users[1] and "마지막 줄" in llm.users[1]


def test_listener_issue_triggers_rewrite():
    sb = _sb()
    odd = _script(sb, "민지는 늦었어요.", "문자에 울었어요.", "결국 웃었어요.")
    good = _script(sb, "민지는 늦었어요.", "지하철에서 문자를 보냈어요.", "결국 웃었어요.")
    llm = _LLM(odd, {"issues": ["컷 2가 어색하다."]}, good, {"issues": []})
    out = asyncio.run(polish_narration(sb, _diary(), llm=llm))
    assert out.cuts[1].narration == "지하철에서 문자를 보냈어요."
    assert "컷 2가 어색하다." in llm.users[2]


def test_comma_ending_shortens_gap_only_when_voice_follows(tmp_path):
    sb = _sb()
    wav = tmp_path / "v.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1), f.setsampwidth(2), f.setframerate(1000), f.writeframes(b"\0\0" * 2000)
    cuts = list(sb.cuts)
    cuts[0] = cuts[0].model_copy(update={"narration": "민지는 늦게 나왔는데,"})
    sb = sb.model_copy(update={"cuts": cuts})
    st = Settings(_env_file=None)
    lengths = edit_lengths(sb, settings=st, narrations={c.index: wav for c in cuts}, voice_of={},
                           hold={cuts[0].index}, delay=0.3)
    assert lengths[0] == 2.7  # 0.3 + 2초 + 0.4
    assert lengths[1] == 3.4  # 0.3 + 2초 + 1.1
