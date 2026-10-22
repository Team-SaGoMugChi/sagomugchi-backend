"""6-1. 대사 더빙 — 대사 컷의 목소리를 인물마다 정해진 TTS 목소리로 바꾼다.

Veo는 대사 컷에서 말하는 사람의 입은 맞게 움직이지만, 목소리는 엉뚱하게 붙이는 일이 잦다
(남자 인물이 여자 목소리로 말하거나 두 사람 목소리가 뒤바뀐다). 또 대본에 없는 짧은 말을
앞에 덧붙이기도 한다. 그래서 그림·입 모양은 Veo 것을 쓰고 소리만 바꾼다:

  1. Veo 오디오에서 말소리가 나는 구간을 찾는다 — 입이 움직이는 시각이다.
  2. 대사 줄마다 그 인물의 TTS 목소리로 읽는다. 인물마다 목소리가 정해져 컷이 바뀌어도 같다.
  3. TTS를 그 구간 시각에 맞춰 놓고(조금 빠르게·느리게 맞춤), Veo의 말소리는 줄인다.
     말소리가 아닌 공간 소리(룸톤)는 그대로 남는다.

말소리 구간을 대사 줄 수만큼 못 찾으면 첫 말소리부터(없으면 컷 시작 조금 뒤부터) 차례로 놓는다.
TTS가 실패하면 그 컷은 Veo 오디오를 그대로 쓴다(compose가 고른다).

dialogue_voice="auto"(기본)는 더빙 전에 Veo 목소리를 먼저 들어 본다(ListenProvider). 대본대로 말했고
목소리 성별이 인물과 맞으면 더빙하지 않고 Veo 목소리를 쓴다 — 입 모양과 가장 잘 맞는다.
말을 덧붙였거나, 대본과 다르거나, 성별이 다르거나, 들을 수 없으면 그 컷만 더빙한다.
판단은 cuts/NN/voice_check.json에 남는다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import numpy as np

from ..config import Settings
from ..errors import VideomakeError
from ..job import JobStore
from ..models import Cut, Storyboard
from ..prompts import PromptLibrary
from ..providers.base import HeardSpeech, ListenProvider, TTSProvider
from .cut_images import voice_off_screen

log = logging.getLogger(__name__)

# Gemini TTS 목소리. 나레이션 목소리(settings.tts_voice)와 겹치면 건너뛴다.
MALE_VOICES = ("Puck", "Charon", "Orus", "Fenrir")
FEMALE_VOICES = ("Kore", "Aoede", "Despina", "Zephyr")

ANALYSIS_RATE = 16_000
FRAME_SECONDS = 0.02
MERGE_GAP_SECONDS = 0.35  # 이보다 짧은 쉼은 한 줄 안의 쉼으로 본다
MIN_SPEECH_SECONDS = 0.25  # 이보다 짧은 소리는 말이 아니라 잡음으로 본다
TEMPO_MIN, TEMPO_MAX = 0.85, 1.35  # 구간에 맞춰 늘이고 줄이는 한계 — 넘으면 어색하게 들린다
# 대사 한 줄을 몇 번 읽혀 입 움직임 길이에 가장 가까운 것을 고른다. TTS는 한 번에 약 $0.002.
TAKES = 3
TEMPO_HARD_MAX = 1.45  # 컷 끝을 넘을 때만 여기까지 빠르게
LINE_GAP_SECONDS = 0.15
FALLBACK_ONSET_SECONDS = 0.8
END_MARGIN_SECONDS = 0.15
SPEECH_LEVEL_DB = -13.0  # 나레이션(Gemini TTS)이 말할 때의 크기와 비슷하게
PEAK_LIMIT_DB = -1.0
MAX_GAIN_DB = 12.0
VEO_VOICE_GAIN = 0.015  # 바꾼 구간의 Veo 말소리를 이만큼으로 줄인다(약 -36dB)
# Veo 목소리 확인 기준 (dialogue_voice="auto")
# 대본보다 이만큼(또는 대본의 10%) 넘게 길게 들리면 말을 덧붙인 것. 20%로는 대사 끝에 붙은
# "한기유"(3글자)를 놓쳤다(2026-10-21).
EXTRA_CHARS_MIN = 2
EXTRA_CHARS_RATIO = 0.1
MAX_SCRIPT_ERROR = 0.25  # 글자 오류율이 이보다 크면 대본과 다른 말
LISTEN_PRICE_PER_CUT = Decimal("0.001")


@dataclass(frozen=True)
class Slot:
    start: float
    tempo: float
    seconds: float  # 배치 후 길이(원래 길이 / tempo)


def voice_gender(description: str) -> str | None:
    text = description.lower()
    if re.search(r"\b(woman|girl|female|mother|mom|grandmother|lady|sister)\b", text):
        return "f"
    if re.search(r"\b(man|boy|male|father|dad|grandfather|gentleman|brother)\b", text):
        return "m"
    return None


def assign_voices(sb: Storyboard, narrator_voice: str) -> dict[str, str]:
    """인물 이름 → TTS 목소리. 같은 성별끼리도 서로 다른 목소리를 준다."""
    pools = {
        "m": [v for v in MALE_VOICES if v != narrator_voice],
        "f": [v for v in FEMALE_VOICES if v != narrator_voice],
    }
    used: dict[str, int] = {"m": 0, "f": 0}
    voices: dict[str, str] = {}
    for person in [sb.protagonist, *sb.supporting]:
        gender = voice_gender(f"{person.voice} {person.appearance}") or "f"
        pool = pools[gender]
        voices[person.name] = pool[used[gender] % len(pool)]
        used[gender] += 1
    return voices


def _letters(text: str) -> str:
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", text or "")


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def veo_voice_ok(script: str, heard: HeardSpeech, gender: str | None) -> tuple[bool, str]:
    """Veo가 만든 대사 목소리를 그대로 써도 되는가. (판단, 이유)"""
    ref, hyp = _letters(script), _letters(heard.text)
    if not hyp:
        return False, "말소리를 못 들음"
    if gender and heard.voice and heard.voice != gender:
        return False, f"목소리 성별이 다름({heard.voice}, 인물 {gender})"
    if len(hyp) - len(ref) > max(EXTRA_CHARS_MIN, len(ref) * EXTRA_CHARS_RATIO):
        return False, "대본에 없는 말을 덧붙임"
    error = _edit_distance(ref, hyp) / max(len(ref), 1)
    if error > MAX_SCRIPT_ERROR:
        return False, f"대본과 다른 말(글자 오류율 {error:.0%})"
    return True, f"대본대로 말함(글자 오류율 {error:.0%})"


def spoken_text(text: str) -> str:
    """끝 문장부호가 없으면 마침표를 붙인다. 없으면 TTS가 질문처럼 끝을 올려 읽는 일이 잦다."""
    text = text.strip()
    return text if text.endswith((".", "?", "!", "…", "~")) else text + "."


def speech_segments(samples: np.ndarray, rate: int = ANALYSIS_RATE) -> list[tuple[float, float]]:
    """말소리가 나는 구간(초). 소리 크기로 찾는다 — 대사 컷의 Veo 오디오는 대사와 룸톤뿐이다."""
    frame = int(rate * FRAME_SECONDS)
    if len(samples) < frame * 5:
        return []
    n = len(samples) // frame
    frames = samples[: n * frame].astype(np.float64).reshape(n, frame) / 32768.0
    db = 20 * np.log10(np.sqrt(np.mean(frames**2, axis=1)) + 1e-9)
    floor, peak = np.percentile(db, 10), np.percentile(db, 98)
    if peak - floor < 12:  # 말소리가 뚜렷하지 않다
        return []
    voiced = db > max(floor + 10, peak - 22)

    raw: list[list[float]] = []
    for i, on in enumerate(voiced):
        t = i * FRAME_SECONDS
        if on and raw and t - raw[-1][1] <= MERGE_GAP_SECONDS:
            raw[-1][1] = t + FRAME_SECONDS
        elif on:
            raw.append([t, t + FRAME_SECONDS])
    return [(round(a, 2), round(b, 2)) for a, b in raw if b - a >= MIN_SPEECH_SECONDS]


def target_lengths(segments: list[tuple[float, float]], n: int) -> list[float | None]:
    """대사 줄마다 입이 움직이는 시간(초). plan_slots와 같은 방식으로 구간을 고른다. 모르면 None."""
    if len(segments) < n:
        return [None] * n
    chosen = sorted(sorted(segments, key=lambda s: s[1] - s[0], reverse=True)[:n])
    return [round(b - a, 3) for a, b in chosen]


def pick_take(durations: list[float], target: float | None) -> int:
    """입 움직임 길이(target)에 가장 가까운 읽기. target을 모르면 가장 짧은 읽기."""
    if target is None:
        return min(range(len(durations)), key=lambda i: durations[i])
    return min(range(len(durations)), key=lambda i: abs(durations[i] - target))


def plan_slots(
    segments: list[tuple[float, float]], durations: list[float], clip_seconds: float
) -> list[Slot]:
    """대사 줄마다 놓을 시각과 빠르기. 말소리 구간이 줄 수보다 많으면 긴 구간을 고른다
    (Veo가 덧붙인 짧은 말은 버려진다). 모자라면 첫 말소리부터 차례로 놓는다."""
    n = len(durations)
    if len(segments) >= n:
        chosen = sorted(sorted(segments, key=lambda s: s[1] - s[0], reverse=True)[:n])
        targets = [(a, b - a) for a, b in chosen]
    else:
        onset = segments[0][0] if segments else FALLBACK_ONSET_SECONDS
        targets = [(onset, d) for d in durations]

    slots: list[Slot] = []
    prev_end = 0.0
    for (start, length), dur in zip(targets, durations):
        tempo = min(max(dur / max(length, 0.1), TEMPO_MIN), TEMPO_MAX)
        at = max(start, prev_end + LINE_GAP_SECONDS) if slots else start
        slots.append(Slot(start=round(at, 3), tempo=round(tempo, 3), seconds=dur / tempo))
        prev_end = at + dur / tempo

    # 컷 끝을 넘으면 전체를 조금 더 빠르게 읽고 앞으로 당긴다. 그래도 넘으면 마지막 줄 끝이 잘린다.
    limit = clip_seconds - END_MARGIN_SECONDS
    overflow = prev_end - limit
    if overflow > 0:
        spoken = sum(s.seconds for s in slots)
        factor = spoken / max(spoken - overflow, 0.1)
        packed: list[Slot] = []
        at = min(slots[0].start, max(limit - spoken / factor - LINE_GAP_SECONDS * (n - 1), 0.2))
        for slot, dur in zip(slots, durations):
            tempo = min(slot.tempo * factor, TEMPO_HARD_MAX)
            packed.append(Slot(start=round(at, 3), tempo=round(tempo, 3), seconds=dur / tempo))
            at += dur / tempo + LINE_GAP_SECONDS
        slots = packed
    return slots


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise VideomakeError("ffmpeg를 찾을 수 없다. `brew install ffmpeg`")
    return exe


def _run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-10:])
        raise VideomakeError(f"ffmpeg 실패:\n{tail}")


def _load_mono(src: Path, seconds: float) -> np.ndarray:
    proc = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", str(src), "-t", str(seconds), "-vn",
         "-ac", "1", "-ar", str(ANALYSIS_RATE), "-f", "s16le", "-"],
        capture_output=True, check=False, stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return np.zeros(0, dtype=np.int16)
    return np.frombuffer(proc.stdout, dtype=np.int16)


def level_gain_db(samples: np.ndarray, rate: int) -> float:
    """말소리가 나는 부분의 크기를 나레이션과 같은 SPEECH_LEVEL_DB로 맞추는 이득(dB).
    봉우리는 뒤의 리미터가 누른다. 잡음을 키우지 않게 MAX_GAIN_DB까지만 올린다."""
    x = samples.astype(np.float64) / 32768.0
    frame = max(int(rate * FRAME_SECONDS), 1)
    n = len(x) // frame
    if n == 0:
        return 0.0
    frames = x[: n * frame].reshape(n, frame)
    db = 20 * np.log10(np.sqrt(np.mean(frames**2, axis=1)) + 1e-9)
    active = frames[db > -40]
    if active.size == 0:
        return 0.0
    level = 20 * np.log10(np.sqrt(np.mean(active**2)) + 1e-9)
    return float(min(SPEECH_LEVEL_DB - level, MAX_GAIN_DB))


def _trim_silence(src: Path, dest: Path) -> float:
    """TTS 앞뒤의 빈 소리를 잘라 내고 크기를 나레이션에 맞춘다. 남은 길이(초)를 돌려준다.

    대사는 말투(조심스럽게 등)에 따라 TTS가 작게 읽어 나레이션보다 6~8dB 작게 들렸다."""
    edge = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05"
    trimmed = dest.with_name(dest.stem + "_trim.wav")
    _run([_ffmpeg(), "-y", "-i", str(src), "-af",
          f"{edge},areverse,{edge},areverse", str(trimmed)])
    with wave.open(str(trimmed), "rb") as wf:
        rate = wf.getframerate()
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    gain = level_gain_db(samples, rate)
    limit = 10 ** (PEAK_LIMIT_DB / 20)
    _run([_ffmpeg(), "-y", "-i", str(trimmed), "-af",
          f"volume={gain:.2f}dB,alimiter=limit={limit:.3f}:attack=2:release=50:level=false",
          str(dest)])
    trimmed.unlink(missing_ok=True)
    return len(samples) / rate


def _mix(
    veo: Path | None,
    lines: list[Path],
    slots: list[Slot],
    segments: list[tuple[float, float]],
    dest: Path,
    clip_seconds: float,
) -> None:
    args = [_ffmpeg(), "-y"]
    filters: list[str] = []
    labels: list[str] = []
    k = 0
    if veo is not None:
        args += ["-i", str(veo)]
        duck = "+".join(f"between(t,{a - 0.05:.2f},{b + 0.1:.2f})" for a, b in segments)
        chain = "aresample=48000,aformat=channel_layouts=stereo"
        if duck:
            chain += f",volume=volume={VEO_VOICE_GAIN}:enable='{duck}'"
        filters.append(f"[0:a]{chain}[bed]")
        labels.append("[bed]")
        k = 1
    for i, (path, slot) in enumerate(zip(lines, slots)):
        args += ["-i", str(path)]
        delay = int(slot.start * 1000)
        filters.append(
            f"[{k + i}:a]atempo={slot.tempo},aresample=48000,"
            f"aformat=channel_layouts=stereo,adelay={delay}:all=1[l{i}]"
        )
        labels.append(f"[l{i}]")
    filters.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
        f"apad=whole_dur={clip_seconds},atrim=0:{clip_seconds}[out]"
    )
    args += ["-filter_complex", ";".join(filters), "-map", "[out]",
             "-ar", "48000", "-ac", "2", str(dest)]
    _run(args)


async def dub_dialogue(
    sb: Storyboard,
    *,
    tts: TTSProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    force: bool = False,
    concurrency: int = 3,
    listen: ListenProvider | None = None,
) -> dict[int, Path]:
    """대사 컷마다 더빙한 오디오(cuts/NN/dialogue.wav). 실패한 컷과 Veo 목소리를 그대로 쓰는 컷은 빠진다."""
    cuts = [c for c in sb.cuts if c.is_dialogue]
    if not cuts or settings.dialogue_voice == "veo":
        return {}
    voices = assign_voices(sb, settings.tts_voice)
    sem = asyncio.Semaphore(concurrency)
    started = time.perf_counter()

    async def line_audio(cut: Cut, k: int, target: float | None) -> Path:
        """대사 한 줄을 TAKES번 읽혀 입 움직임 길이에 가장 가까운 것을 line_N.wav로 남긴다.
        같은 대사도 읽을 때마다 길이가 0.5초 넘게 달라진다."""
        line = cut.dialogue[k]
        chosen = job.cut_dir(cut.index) / f"line_{k + 1}.wav"
        if chosen.exists() and not force:
            return chosen
        profile = sb.character(line.speaker)
        style = prompts.render(
            "dialogue_style.j2",
            text=spoken_text(line.text),
            voice=getattr(profile, "voice", ""),
            mood=cut.mood,
        )

        async def take(t: int) -> tuple[Path, float]:
            raw = job.cut_dir(cut.index) / f"line_{k + 1}_take{t}_raw.wav"
            trimmed = job.cut_dir(cut.index) / f"line_{k + 1}_take{t}.wav"
            async with sem:
                result = await tts.synthesize(
                    text=line.text, dest=raw, voice=voices.get(line.speaker, MALE_VOICES[0]),
                    style_prompt=style,
                )
            job.record_cost(f"cut{cut.index}_line{k + 1}_tts{t}", result.cost_usd)
            return trimmed, _trim_silence(raw, trimmed)

        takes = await asyncio.gather(*(take(t) for t in range(1, TAKES + 1)))
        best = pick_take([d for _, d in takes], target)
        shutil.copy2(takes[best][0], chosen)
        log.info(
            "컷 %d 대사 %d: 입 %ss, 읽기 %s → %d번째",
            cut.index, k + 1, target, [round(d, 2) for _, d in takes], best + 1,
        )
        return chosen

    async def keep_veo_voice(cut: Cut) -> bool:
        """Veo 목소리를 들어 보고 그대로 써도 되면 True. 들을 수 없으면 False(더빙)."""
        record = job.cut_dir(cut.index) / "voice_check.json"
        if record.exists() and not force:
            return bool(json.loads(record.read_text(encoding="utf-8"))["keep_veo_voice"])
        script = " ".join(line.text for line in cut.dialogue)
        genders = {voice_gender(f"{p.voice} {p.appearance}") for p in
                   (sb.character(line.speaker) for line in cut.dialogue) if p}
        gender = genders.pop() if len(genders) == 1 else None
        clip = job.cut_dir(cut.index) / "veo_listen.wav"
        try:
            _run([_ffmpeg(), "-y", "-i", str(job.cut_video(cut.index)), "-t", str(cut.duration_seconds),
                  "-vn", "-ar", str(ANALYSIS_RATE), "-ac", "1", str(clip)])
            async with sem:
                heard = await listen.listen(audio=clip)
            job.record_cost(f"cut{cut.index}_listen", LISTEN_PRICE_PER_CUT)
        except Exception as exc:
            log.warning("컷 %d Veo 목소리를 듣지 못해 더빙한다: %s", cut.index, exc)
            return False
        ok, reason = veo_voice_ok(script, heard, gender)
        record.write_text(json.dumps({"keep_veo_voice": ok, "reason": reason, "script": script,
                                      "heard": heard.text, "heard_voice": heard.voice, "gender": gender},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("컷 %d 대사 목소리: %s — %s (들림: %s)", cut.index,
                 "Veo 그대로" if ok else "TTS 더빙", reason, heard.text)
        return ok

    async def one(cut: Cut) -> tuple[int, Path | None]:
        dest = job.cut_dialogue(cut.index)
        if settings.dialogue_voice == "auto" and listen is not None and await keep_veo_voice(cut):
            dest.unlink(missing_ok=True)
            return cut.index, None
        if dest.exists() and not force:
            log.info("컷 %d 대사 더빙 캐시 재사용", cut.index)
            return cut.index, dest
        try:
            src = job.cut_video(cut.index)
            # 화면 밖 목소리(전화 등)는 맞출 입이 없다. Veo 소리에서 말소리를 찾지 않고
            # 원래 속도로 컷 시작 조금 뒤부터 놓는다(입에 맞추다 1.45배 빨라진 적이 있다).
            off_screen = voice_off_screen(sb, cut)
            segments = [] if off_screen else speech_segments(_load_mono(src, cut.duration_seconds))
            targets = target_lengths(segments, len(cut.dialogue))
            lines = await asyncio.gather(
                *(line_audio(cut, k, targets[k]) for k in range(len(cut.dialogue)))
            )
            durations = []
            for path in lines:
                with wave.open(str(path), "rb") as wf:
                    durations.append(wf.getnframes() / wf.getframerate())
            slots = plan_slots(segments, durations, cut.duration_seconds)
            veo = job.cut_dir(cut.index) / "veo_audio.wav"
            proc = subprocess.run(
                [_ffmpeg(), "-y", "-i", str(src), "-t", str(cut.duration_seconds), "-vn",
                 "-ar", "48000", "-ac", "2", str(veo)],
                capture_output=True, check=False, stdin=subprocess.DEVNULL,
            )
            bed = veo if proc.returncode == 0 and veo.exists() else None
            _mix(bed, list(lines), slots, segments, dest, cut.duration_seconds)
        except Exception:
            log.exception("컷 %d 대사 더빙 실패 — Veo 목소리를 그대로 쓴다", cut.index)
            return cut.index, None
        log.info(
            "컷 %d 대사 더빙: 말소리 구간 %s → %s",
            cut.index, segments, [(s.start, s.tempo) for s in slots],
        )
        return cut.index, dest

    pairs = await asyncio.gather(*(one(c) for c in cuts))
    log.info("대사 더빙 %.1fs (목소리: %s)", time.perf_counter() - started, voices)
    return {i: p for i, p in pairs if p is not None}
