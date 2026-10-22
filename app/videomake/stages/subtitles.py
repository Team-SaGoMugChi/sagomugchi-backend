"""7-1. 자막 — 완성 영상과 같은 시각의 WebVTT 자막(subtitles.vtt).

영상에 글자를 박지 않는다(앱에서 켜고 끌 수 있게 따로 준다). 시각은 합성(compose)과 같은 계산을 쓴다.
  - 나레이션: 그 컷 시작 + NARRATION_DELAY_MS부터 나레이션 길이만큼.
  - 대사: 실제로 나가는 소리(더빙 또는 영상 모델 목소리)에서 말소리 구간을 찾아 그 동안.
    못 찾으면 컷 시작 조금 뒤부터 컷 끝 조금 전까지.
"""

from __future__ import annotations

import logging
import wave
from dataclasses import dataclass
from pathlib import Path

from ..job import JobStore
from ..models import Storyboard
from .dialogue_voice import ANALYSIS_RATE, FALLBACK_ONSET_SECONDS, _load_mono, speech_segments

log = logging.getLogger(__name__)

LINE_CHARS = 16  # 세로 화면 한 줄 글자 수
END_GAP = 0.2


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def _wrap(text: str, width: int = LINE_CHARS) -> str:
    """띄어쓰기 단위로 줄을 나눈다(최대 두 줄 정도가 되게)."""
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    if cur:
        lines.append(cur)
    if len(lines) > 1 and len(lines[-1]) <= 3:  # "해." 한 글자만 다음 줄로 넘어가지 않게
        tail = lines.pop()
        lines[-1] = f"{lines[-1]} {tail}"
    return "\n".join(lines)


def _wav_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return None


def build_cues(
    sb: Storyboard,
    *,
    starts: list[float],
    total: float,
    narrations: dict[int, Path],
    voices: dict[int, Path],
    narration_delay: float,
) -> list[Cue]:
    """voices: 대사 컷마다 실제로 나가는 소리 파일(더빙 또는 영상 소리)."""
    cues: list[Cue] = []
    for cut, start in zip(sb.cuts, starts):
        end_of_cut = start + cut.duration_seconds
        if cut.narration and cut.index in narrations:
            seconds = _wav_seconds(narrations[cut.index])
            if seconds:
                s = start + narration_delay
                cues.append(Cue(s, min(s + seconds, total), cut.narration))
        elif cut.dialogue:
            segments = []
            src = voices.get(cut.index)
            if src is not None and src.exists():
                segments = speech_segments(_load_mono(src, cut.duration_seconds), ANALYSIS_RATE)
            if segments:
                s, e = start + segments[0][0], start + segments[-1][1]
            else:
                s, e = start + FALLBACK_ONSET_SECONDS, end_of_cut - END_GAP
            text = " ".join(line.text for line in cut.dialogue)
            cues.append(Cue(s, min(max(e, s + 1.0), total), text))
    return cues


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def to_vtt(cues: list[Cue]) -> str:
    body = ["WEBVTT", ""]
    for k, c in enumerate(cues, 1):
        body += [str(k), f"{_ts(c.start)} --> {_ts(c.end)}", _wrap(c.text), ""]
    return "\n".join(body)


def write_subtitles(sb: Storyboard, job: JobStore, **kwargs) -> Path:
    cues = build_cues(sb, **kwargs)
    job.subtitles_path.write_text(to_vtt(cues), encoding="utf-8")
    log.info("자막 %d줄 → %s", len(cues), job.subtitles_path.name)
    return job.subtitles_path
