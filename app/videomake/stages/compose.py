"""7. Compositor — 컷 크로스페이드 + 나레이션·대사를 한 시간축에 배치 + 페이드 → final.mp4

컷은 CROSSFADE_SECONDS만큼 겹쳐 넘긴다(짧은 컷이 툭툭 끊겨 보이지 않게).
소리는 컷마다 따로 붙이지 않고 영상 전체 시간축에 놓는다:
  - 나레이션: 그 컷이 시작하고 NARRATION_DELAY_MS 뒤. 뒤따르는 무음 컷까지 이어서 깔릴 수 있다
    (글자 수는 스토리보드 단계에서 그 구간 안에 들어가게 막는다).
  - 대사 컷: 인물별 TTS로 더빙한 오디오(dialogue_voice.py)를 그 컷 구간에. 더빙이 없으면 Veo 목소리.
  - 장면 소리(veo_audio="ambient", 기본): 대사 없는 컷의 Veo 소리를 컷마다 같은 크기로 맞춰 깐다.
    나레이션이 깔리는 컷은 작게(veo_ambient_gain_db), 목소리 없는 컷은 조금 크게. "mute"면 버린다.

Veo는 오디오 생성을 끌 수 없다(Developer API에 generate_audio가 없다). 그래서 여기서 고른다.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
import wave
from pathlib import Path

import numpy as np

from ..config import CROSSFADE_SECONDS, Settings
from ..errors import VideomakeError
from ..job import JobStore
from ..models import Cut, EditPlan, Stage, Storyboard
from .dialogue_voice import _load_mono, speech_segments
from .narration_flow import continues_into_next
from .subtitles import write_subtitles

log = logging.getLogger(__name__)

NARRATION_DELAY_MS = 400  # tight_edit=False일 때. 켜져 있으면 settings.narration_delay_ms
# 샷을 나눈 컷을 줄일 때, 이미 시작한 샷은 이만큼은 보여준다(너무 짧으면 화면이 번쩍인다).
LAST_SHOT_MIN_SECONDS = 1.5
MUSIC_FADE_IN = 1.0
MUSIC_FADE_OUT = 1.8
AUDIO_RATE = 48_000
FPS = 24

_FRAME_SIZES = {
    ("9:16", "720p"): (720, 1280),
    ("9:16", "1080p"): (1080, 1920),
    ("16:9", "720p"): (1280, 720),
    ("16:9", "1080p"): (1920, 1080),
}


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise VideomakeError("ffmpeg를 찾을 수 없다. `brew install ffmpeg`")
    return exe


def _run(args: list[str]) -> None:
    # ffmpeg가 터미널 키 입력을 읽지 않게 stdin을 끊는다(서버·백그라운드 실행).
    proc = subprocess.run(args, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise VideomakeError(f"ffmpeg 실패:\n{tail}")


def cut_starts(seconds: list[int], crossfade: float = CROSSFADE_SECONDS) -> list[float]:
    """크로스페이드로 겹친 최종 영상에서 각 컷이 시작하는 시각(초)."""
    starts, at = [], 0.0
    for s in seconds:
        starts.append(round(at, 3))
        at += s - crossfade
    return starts


def _prepare_video(
    src: Path, dest: Path, *, seconds: float, size: tuple[int, int], card: Path | None = None
) -> None:
    """xfade는 크기·프레임·픽셀 형식이 같아야 한다. 컷마다 같은 규격으로 맞추고 소리는 뺀다.
    card: 컷 첫머리 TIME_CARD_SECONDS 동안 위에 얹을 시간 글자 그림(투명 PNG, 화면 크기)."""
    w, h = size
    base = f"scale={w}:{h},setsar=1,fps={FPS}"
    if card is None:
        video = ["-vf", f"{base},format=yuv420p"]
    else:
        video = [
            "-i", str(card), "-filter_complex",
            f"[0:v]{base}[v];[v][1:v]overlay=0:0:enable='lt(t,{TIME_CARD_SECONDS})',format=yuv420p",
        ]
    _run([
        _ffmpeg(), "-y", "-i", str(src), *video, "-t", str(seconds), "-an",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(dest),
    ])


# 시간이 건너뛴 컷 첫머리에 띄우는 글자("다음 날"). 릴스처럼 노란 굵은 글씨에 검은 테두리, 화면 위쪽.
TIME_CARD_SECONDS = 1.6
_CARD_FONTS = (
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6),  # macOS (index 6 = Bold)
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),  # Debian·Ubuntu fonts-noto-cjk (KR)
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 1),
)


def _time_card(text: str, dest: Path, *, size: tuple[int, int]) -> Path | None:
    """시간 글자를 투명 PNG로 그린다. 한글 글꼴이 없으면 None(글자 없이 컷만 쓴다)."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = size
    font = None
    for path, index in _CARD_FONTS:
        if Path(path).exists():
            font = ImageFont.truetype(path, int(w * 0.12), index=index)
            break
    if font is None:
        log.warning("한글 글꼴이 없어 시간 글자(%s)를 넣지 않는다", text)
        return None
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(image).text(
        (w // 2, int(h * 0.2)), text, font=font, anchor="mm", fill=(255, 221, 51, 255),
        stroke_width=max(4, w // 120), stroke_fill=(0, 0, 0, 255),
    )
    image.save(dest)
    return dest


def _extract_audio(src: Path, dest: Path, *, seconds: float) -> bool:
    """Veo 오디오를 따로 꺼낸다. 오디오가 없는 영상이면 False."""
    proc = subprocess.run(
        [
            _ffmpeg(), "-y", "-i", str(src), "-t", str(seconds), "-vn",
            "-ar", str(AUDIO_RATE), "-ac", "2", str(dest),
        ],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
    )
    return proc.returncode == 0 and dest.exists() and dest.stat().st_size > 0


SPEECH_PAD_SECONDS = 0.15  # 지운 말소리 앞뒤로 조금 더 지운다(말끝이 새지 않게)


def _mute_speech(path: Path, *, seconds: float) -> list[tuple[float, float]]:
    """대사 없는 컷의 Veo 소리에서 말소리 구간을 지운다(주변 소리는 남긴다). 지운 구간을 돌려준다.

    나레이션 컷의 장면 소리에 Veo가 지어낸 "네", "어"가 섞여 나레이션 사이사이에 들렸다
    (2026-11 할머니 텃밭: 컷 1·3 "네", 컷 5 뒤 "어", 끝에 "네")."""
    spans = speech_segments(_load_mono(path, seconds))
    if not spans:
        return []
    spans = [(max(0.0, a - SPEECH_PAD_SECONDS), min(seconds, b + SPEECH_PAD_SECONDS)) for a, b in spans]
    return spans if _mute_spans(path, spans) else []


BLIP_MAX_SECONDS = 0.6  # 대사 앞에 이만큼 짧게 따로 들리는 소리("야", "네")는 지어낸 말로 본다
BLIP_GAP_SECONDS = 0.3


def _mute_leading_blip(path: Path, *, seconds: float) -> None:
    """대사 컷 맨 앞, 대사와 떨어져 짧게 들리는 소리를 지운다(2026-11 할머니 텃밭 컷 4 "약 … 이건 연한")."""
    spans = speech_segments(_load_mono(path, seconds))
    if len(spans) >= 2 and spans[0][1] - spans[0][0] <= BLIP_MAX_SECONDS \
            and spans[1][0] - spans[0][1] >= BLIP_GAP_SECONDS:
        _mute_spans(path, [(max(0.0, spans[0][0] - 0.05), spans[0][1] + 0.05)])


SCRIPT_END_PAD_SECONDS = 0.12
VOICE_GAP_SECONDS = 0.5  # 다른 목소리 사이에 쉬는 최소 틈  # 대본 마지막 글자가 끝나고 조금 뒤부터 지운다


def _mute_spans(path: Path, spans: list[tuple[float, float]]) -> bool:
    """소리 파일에서 그 구간들만 소리를 0으로 만든다(길이는 그대로)."""
    enable = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in spans)
    muted = path.with_name(f"{path.stem}_muted{path.suffix}")
    proc = subprocess.run(
        [_ffmpeg(), "-y", "-i", str(path), "-af", f"volume=0:enable='{enable}'", str(muted)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
    )
    if proc.returncode == 0 and muted.exists():
        muted.replace(path)
        return True
    return False


def _level_gain(path: Path, target_db: float, max_gain_db: float = 20.0) -> float:
    """장면 소리를 target_db(RMS)로 맞추는 이득. 거의 무음이면 키우지 않는다(잡음만 커진다)."""
    with wave.open(str(path), "rb") as wf:
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    if samples.size == 0:
        return target_db
    rms = float(np.sqrt(np.mean((samples.astype(np.float64) / 32768.0) ** 2)))
    level = 20 * np.log10(rms + 1e-9)
    if level < -60:
        return 0.0
    return min(target_db - level, max_gain_db)


def _wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def edit_lengths(
    sb: Storyboard,
    *,
    settings: Settings,
    narrations: dict[int, Path],
    voice_of: dict[int, Path],
    hold: set[int],
    delay: float,
    script_ends: dict[int, float] | None = None,
    clean_until: dict[int, float] | None = None,
) -> list[float]:
    """컷마다 최종 영상에서 쓸 길이(초). 목소리가 끝난 뒤의 정적을 잘라낸다(쇼츠 편집).

    자르지 않는 컷: 무음 컷(화면만 보여주는 동작), 편집 계획이 고른 hold 컷, 나레이션이
    이 컷보다 길어 뒤 컷까지 이어지는 컷. 샷을 나눈 컷은 목소리가 끝날 때 시작한 샷까지만 남긴다.
    voice_of: 대사 컷마다 실제로 나가는 소리(더빙 파일 또는 영상).
    script_ends: 대본 뒤에 Veo가 말을 덧붙인 컷 — 대본이 끝나는 시각. 덧붙인 말은 늘 잘라 낸다(hold여도).
    clean_until: 영상 도중 화면 끝에 낯선 사람이 들어오는 컷 — 그 앞까지만 쓴다(목소리는 끝까지 남긴다).
    """
    script_ends = script_ends or {}
    clean_until = clean_until or {}
    lengths: list[float] = []
    for pos, cut in enumerate(sb.cuts):
        full = float(cut.duration_seconds)
        need = script_ends.get(cut.index) or _voice_end(cut, narrations, voice_of, delay)
        if cut.index in script_ends:
            # 덧붙인 말이 곧바로 이어져서 평소 여유(edit_tail_seconds)를 두면 첫 글자가 들렸다.
            full = min(full, need + settings.edit_flow_tail_seconds)
        if cut.index in clean_until:
            full = min(full, max(clean_until[cut.index], need or 0.0, settings.edit_min_cut_seconds))
        # 쉼표로 끝난 나레이션이 다음 목소리로 이어지면 hold 컷이어도 짧게 넘긴다.
        flows = continues_into_next(cut) and pos + 1 < len(sb.cuts) and not sb.cuts[pos + 1].is_silent
        if not settings.tight_edit or need is None or (cut.index in hold and not flows):
            lengths.append(full)
            continue
        # 대사를 주고받으면(다음 컷도 대사) 한 줄이 끝나자마자 상대에게 넘긴다(릴스의 한 대사 한 샷 리듬).
        exchange = cut.is_dialogue and pos + 1 < len(sb.cuts) and sb.cuts[pos + 1].is_dialogue
        tail = (settings.edit_flow_tail_seconds if flows
                else settings.edit_exchange_tail_seconds if exchange else settings.edit_tail_seconds)
        end = need + tail
        floor = settings.edit_min_cut_seconds
        # 샷을 나눈 컷: 목소리가 끝날 때 이미 시작한 샷은 잠깐은 보여 주고(번쩍임 방지),
        # 아직 시작하지 않은 샷은 버린다 — 샷을 보여주려고 정적을 남기지 않는다.
        at = 0.0
        for shot in cut.shots:
            if at < end and end - at < LAST_SHOT_MIN_SECONDS:
                floor = max(floor, at + LAST_SHOT_MIN_SECONDS)
            at += shot.seconds
        lengths.append(round(min(full, max(floor, end)), 3))
    return lengths


def _check_value(job: JobStore, index: int, name: str, key: str) -> float | None:
    """cuts/NN/<name>(검사 기록)의 숫자 값. 없으면 None."""
    path = job.cut_dir(index) / name
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _voice_end(cut: Cut, narrations: dict[int, Path], voice_of: dict[int, Path], delay: float) -> float | None:
    """컷 시작부터 목소리가 끝나는 시각. 목소리가 없는 컷(무음 컷)은 None — 자르지 않는다."""
    if cut.narration and cut.index in narrations:
        return delay + _wav_seconds(narrations[cut.index])
    if cut.dialogue and cut.index in voice_of:
        segments = speech_segments(_load_mono(voice_of[cut.index], cut.duration_seconds))
        return segments[-1][1] if segments else None
    return None


MUSIC_DUCK_RAMP_SECONDS = 0.3  # 음악을 줄이고 되돌리는 데 걸리는 시간(뚝 끊기지 않게)


def _duck_music(path: Path, spans: list[tuple[float, float]], *, duck_db: float) -> None:
    """음악 파일에서 목소리가 나오는 구간(파일 기준 초)만 duck_db만큼 줄인다. 앞뒤는 천천히 줄이고 되돌린다."""
    with wave.open(str(path), "rb") as wf:
        params = wf.getparams()
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    rate, channels = params.framerate, params.nchannels
    frames = samples.size // channels
    t = np.arange(frames) / rate
    # 0이면 원래 크기, 1이면 duck_db만큼 줄인다. 구간 밖은 ramp 동안 0으로 내려간다.
    depth = np.zeros(frames)
    ramp = MUSIC_DUCK_RAMP_SECONDS
    for a, b in spans:
        dist = np.maximum(np.maximum(a - t, t - b), 0.0)
        depth = np.maximum(depth, np.clip(1.0 - dist / ramp, 0.0, 1.0))
    gain = 10 ** (duck_db * depth / 20)
    out = samples.reshape(frames, channels).astype(np.float64) * gain[:, None]
    with wave.open(str(path), "wb") as wf:
        wf.setparams(params)
        wf.writeframes(np.clip(out, -32768, 32767).astype(np.int16).tobytes())


def _music_track(src: Path, dest: Path, *, seconds: float) -> None:
    """곡을 구간 길이에 맞춘다. 짧으면 같은 곡을 3초 겹쳐 이어 붙이고, 앞뒤를 부드럽게 넣고 뺀다."""
    with wave.open(str(src), "rb") as wf:
        song = wf.getnframes() / wf.getframerate()
    loops = max(0, int(np.ceil((seconds - song) / max(song - 3.0, 1.0))))
    inputs: list[str] = []
    for _ in range(loops + 1):
        inputs += ["-i", str(src)]
    chain, prev = [], "0:a"
    for k in range(1, loops + 1):
        chain.append(f"[{prev}][{k}:a]acrossfade=d=3[x{k}]")
        prev = f"x{k}"
    out_fade = max(seconds - MUSIC_FADE_OUT, 0)
    chain.append(
        f"[{prev}]atrim=0:{seconds},afade=t=in:st=0:d={MUSIC_FADE_IN},"
        f"afade=t=out:st={out_fade}:d={MUSIC_FADE_OUT},aresample={AUDIO_RATE},"
        "aformat=channel_layouts=stereo[m]"
    )
    _run([_ffmpeg(), "-y", *inputs, "-filter_complex", ";".join(chain), "-map", "[m]", str(dest)])


def compose(
    sb: Storyboard,
    *,
    job: JobStore,
    settings: Settings,
    narrations: dict[int, Path] | None = None,
    dialogues: dict[int, Path] | None = None,
    plan: EditPlan | None = None,
    music: dict[int, Path] | None = None,
) -> Path:
    started = time.perf_counter()
    work = job.dir / "compose"
    work.mkdir(exist_ok=True)
    narrations = narrations or {}
    dialogues = dialogues or {}
    plan = plan or EditPlan()
    music = music or {}
    size = _FRAME_SIZES.get((settings.aspect_ratio, settings.video_resolution), (720, 1280))
    delay_ms = settings.narration_delay_ms if settings.tight_edit else NARRATION_DELAY_MS

    voice_of = {
        c.index: dialogues.get(c.index) or job.cut_video(c.index) for c in sb.cuts if c.is_dialogue
    }
    seconds = edit_lengths(
        sb, settings=settings, narrations=narrations, voice_of=voice_of,
        hold=set(plan.hold_cuts), delay=delay_ms / 1000,
        script_ends={i: t for i in voice_of if (t := _check_value(job, i, "voice_check.json", "script_end"))
                     and i not in dialogues},
        clean_until={c.index: t for c in sb.cuts
                     if (t := _check_value(job, c.index, "video_check.json", "clean_until")) is not None},
    )
    starts = cut_starts(seconds)
    total = round(starts[-1] + seconds[-1], 3) if seconds else 0.0
    x = CROSSFADE_SECONDS

    # 나레이션이 깔리는 컷(나레이션 컷 + 이어지는 무음 컷). 장면 소리는 이 아래에서 작게.
    windows = sb.narration_windows()
    under_voice: set[int] = set()
    for pos, cut in enumerate(sb.cuts):
        if cut.index in windows:
            for nxt in sb.cuts[pos:]:
                if nxt is not cut and not nxt.is_silent:
                    break
                under_voice.add(nxt.index)

    videos: list[Path] = []
    voices: dict[int, Path] = {}  # 대사 컷마다 실제로 나가는 소리(자막 시각용)
    # (파일, 시작 시각 ms, 볼륨 dB)
    audios: list[tuple[Path, int, float]] = []
    narration_at: dict[int, float] = {}  # 나레이션이 실제로 들어가는 시각(자막도 여기에 맞춘다)
    voice_spans: list[tuple[float, float]] = []  # 목소리가 나오는 구간(영상 기준 초). 배경음악을 이 동안 줄인다
    voice_end = -VOICE_GAP_SECONDS  # 지금까지 놓은 목소리가 끝나는 시각(처음엔 없음)
    for cut, start, length in zip(sb.cuts, starts, seconds):
        src = job.cut_video(cut.index)
        if not src.exists():
            raise VideomakeError(f"컷 {cut.index}의 영상이 없다: {src}")
        video = work / f"{cut.index:02d}.mp4"
        card = _time_card(cut.time_card, work / f"{cut.index:02d}_card.png", size=size) if cut.time_card else None
        _prepare_video(src, video, seconds=length, size=size, card=card)
        videos.append(video)

        start_ms = int(start * 1000)
        dubbed = dialogues.get(cut.index) if cut.is_dialogue else None
        if dubbed is not None:
            audios.append((dubbed, start_ms, 0.0))
            voices[cut.index] = dubbed
        elif cut.is_dialogue or settings.veo_audio == "ambient":
            voice = work / f"{cut.index:02d}_veo.wav"
            if _extract_audio(src, voice, seconds=length):
                if cut.is_dialogue:
                    gain = 0.0
                    voices[cut.index] = voice
                    # 컷이 짧아 덧붙인 말을 잘라 내지 못하면 소리만 지운다(2026-11 할머니 텃밭 컷 6 "…먹자 야").
                    _mute_leading_blip(voice, seconds=length)
                    end = _check_value(job, cut.index, "voice_check.json", "script_end")
                    if end is not None and end + SCRIPT_END_PAD_SECONDS < length:
                        _mute_spans(voice, [(end + SCRIPT_END_PAD_SECONDS, length)])
                else:
                    if (muted := _mute_speech(voice, seconds=length)):
                        log.info("컷 %d 장면 소리의 말소리를 지움: %s", cut.index,
                                 ", ".join(f"{a:.1f}~{b:.1f}s" for a, b in muted))
                    target = (
                        settings.veo_ambient_gain_db
                        if cut.index in under_voice
                        else settings.veo_ambient_solo_gain_db
                    )
                    gain = _level_gain(voice, target)
                audios.append((voice, start_ms, gain))
        # 앞사람 목소리가 끝나고 VOICE_GAP_SECONDS는 쉬고 다음 목소리를 놓는다. 할머니 대사가 컷 끝까지 이어진 바로
        # 뒤 0.3초 만에 나레이션이 들어와 겹쳐 들렸다(2026-11 할머니 텃밭 컷 6→7).
        if cut.is_dialogue and (spoken := voices.get(cut.index)) is not None:
            segs = speech_segments(_load_mono(spoken, length))
            end = _check_value(job, cut.index, "voice_check.json", "script_end") if spoken.name.endswith("_veo.wav") else None
            if segs:
                voice_end = start + min(segs[-1][1], end if end is not None else segs[-1][1])
                voice_spans.append((start + segs[0][0], voice_end))
        narration = narrations.get(cut.index)
        if narration is not None and not cut.is_dialogue:
            at = max(start + delay_ms / 1000, voice_end + VOICE_GAP_SECONDS)
            narration_at[cut.index] = at
            audios.append((narration, int(at * 1000), 0.0))
            segs = speech_segments(_load_mono(narration, 30))
            voice_end = at + (segs[-1][1] if segs else 0.0)
            voice_spans.append((at, voice_end))
        log.info("컷 %d 준비 완료 (%.1fs부터, %.2fs)", cut.index, start, length)

    # 배경음악: 편집 계획의 구간마다 한 곡을 깔고, 목소리가 나오는 동안만 줄인다.
    positions = {c.index: pos for pos, c in enumerate(sb.cuts)}
    for k, cue in enumerate(plan.music):
        if k not in music:
            continue
        begin = starts[positions[cue.from_cut]]
        end = min(starts[positions[cue.to_cut]] + seconds[positions[cue.to_cut]], total)
        track = work / f"music{k}.wav"
        _music_track(music[k], track, seconds=round(end - begin, 3))
        gain = _level_gain(track, settings.music_level_db)
        _duck_music(track, [(a - begin, b - begin) for a, b in voice_spans if b > begin and a < end],
                    duck_db=settings.music_duck_db)
        audios.append((track, int(begin * 1000), gain))
        log.info("배경음악 %d: 컷 %d~%d (%.1f~%.1fs)", k, cue.from_cut, cue.to_cut, begin, end)

    args = [_ffmpeg(), "-y"]
    for video in videos:
        args += ["-i", str(video)]
    for path, _, _ in audios:
        args += ["-i", str(path)]
    if not audios:
        args += ["-f", "lavfi", "-t", str(total), "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo"]

    filters: list[str] = []
    # 영상: 컷을 차례로 겹쳐 잇는다. 오프셋은 다음 컷이 시작하는 시각이다.
    prev = "0:v"
    for i in range(1, len(videos)):
        out = f"v{i}"
        filters.append(
            f"[{prev}][{i}:v]xfade=transition=fade:duration={x}:offset={starts[i]}[{out}]"
        )
        prev = out
    fade = settings.fade_seconds
    out_start = max(total - fade, 0)
    filters.append(
        f"[{prev}]fade=t=in:st=0:d={fade},fade=t=out:st={out_start}:d={fade}[vout]"
    )

    # 소리: 각자 시작 시각에 놓고 합친 뒤 영상 길이에 맞춘다.
    first_audio = len(videos)
    if audios:
        labels = []
        for k, (_, at_ms, gain) in enumerate(audios):
            label = f"a{k}"
            filters.append(
                f"[{first_audio + k}:a]aresample={AUDIO_RATE},"
                f"aformat=channel_layouts=stereo,volume={gain}dB,"
                f"adelay={at_ms}:all=1[{label}]"
            )
            labels.append(f"[{label}]")
        filters.append(
            "".join(labels)
            + f"amix=inputs={len(labels)}:duration=longest:normalize=0[mix]"
        )
        mixed = "mix"
    else:
        mixed = f"{first_audio}:a"
    filters.append(
        # apad는 끝을 정해 둔다. 끝없는 apad는 ffmpeg 8.1에서 가끔 멈춘다(6번 중 2번 관측).
        f"[{mixed}]apad=whole_dur={total},atrim=0:{total},"
        f"afade=t=in:st=0:d={fade},afade=t=out:st={out_start}:d={fade}[aout]"
    )

    args += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]", "-t", str(total),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", "2",
        "-movflags", "+faststart",
        str(job.final_path),
    ]
    _run(args)
    try:
        write_subtitles(sb, job, starts=starts, total=total, narrations=narrations, voices=voices,
                        narration_delay=delay_ms / 1000, lengths=seconds, narration_at=narration_at)
    except Exception:  # 자막은 덧붙는 산출물이다. 실패해도 영상은 완성으로 둔다.
        log.exception("자막 만들기 실패 — 영상은 그대로 완성")

    job.record_stage(
        Stage.COMPOSE,
        elapsed_s=time.perf_counter() - started,
        path=str(job.final_path),
        duration_s=total,
    )
    log.info("final.mp4 완성 — %.1fs", total)
    return job.final_path
