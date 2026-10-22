"""자막(WebVTT) — 합성과 같은 시각으로 나레이션·대사 자막을 만든다. 비용 0."""

import wave

from app.videomake.models import Storyboard
from app.videomake.providers import fake
from app.videomake.stages.subtitles import _wrap, build_cues, to_vtt


def _wav(path, seconds):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * seconds))
    return path


def _sb():
    payload = fake.demo_storyboard_payload(2)
    payload["supporting"] = [{"name": "지수", "appearance": "A woman.", "voice": "a woman"}]
    payload["cuts"][0].update(narration="지은은 카페에 늦게 도착했어요.", duration_seconds=6)
    payload["cuts"][1].update(narration="", duration_seconds=4, cast=[{"name": "지수", "position": "right"}],
                              dialogue=[{"speaker": "지수", "text": "왜 늦었어"}])
    return Storyboard.model_validate(payload)


def test_cues_follow_compose_timing(tmp_path):
    sb = _sb()
    cues = build_cues(sb, starts=[0.0, 5.7], total=9.7, narrations={1: _wav(tmp_path / "n.wav", 2.5)},
                      voices={}, narration_delay=0.4)
    assert [c.text for c in cues] == ["지은은 카페에 늦게 도착했어요.", "왜 늦었어"]
    assert cues[0].start == 0.4 and abs(cues[0].end - 2.9) < 1e-6  # 컷 시작 + 0.4초부터 나레이션 길이만큼
    assert 5.7 < cues[1].start < cues[1].end <= 9.7  # 말소리를 못 찾으면 컷 안 기본 구간


def test_vtt_format_and_wrapping():
    from app.videomake.stages.subtitles import Cue

    text = to_vtt([Cue(0.4, 2.9, "익숙한 것들이 하나둘 사라져 허전하고 슬펐어요.")])
    assert text.startswith("WEBVTT\n")
    assert "00:00:00.400 --> 00:00:02.900" in text
    assert all(len(line) <= 16 for line in _wrap("익숙한 것들이 하나둘 사라져 허전하고 슬펐어요.").splitlines())
    assert _wrap("몸이 안 좋아져서 그만두려고 해.") == "몸이 안 좋아져서 그만두려고 해."  # 짧은 꼬리는 붙인다
