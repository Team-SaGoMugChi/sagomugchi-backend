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
from ..models import Stage, Storyboard
from .subtitles import write_subtitles

log = logging.getLogger(__name__)

NARRATION_DELAY_MS = 400  # 컷이 시작하고 잠깐 뒤에 목소리가 들어오는 편이 자연스럽다
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


def _prepare_video(src: Path, dest: Path, *, seconds: int, size: tuple[int, int]) -> None:
    """xfade는 크기·프레임·픽셀 형식이 같아야 한다. 컷마다 같은 규격으로 맞추고 소리는 뺀다."""
    w, h = size
    _run([
        _ffmpeg(), "-y", "-i", str(src), "-t", str(seconds), "-an",
        "-vf", f"scale={w}:{h},setsar=1,fps={FPS},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(dest),
    ])


def _extract_audio(src: Path, dest: Path, *, seconds: int) -> bool:
    """Veo 오디오를 따로 꺼낸다. 오디오가 없는 영상이면 False."""
    proc = subprocess.run(
        [
            _ffmpeg(), "-y", "-i", str(src), "-t", str(seconds), "-vn",
            "-ar", str(AUDIO_RATE), "-ac", "2", str(dest),
        ],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
    )
    return proc.returncode == 0 and dest.exists() and dest.stat().st_size > 0


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


def compose(
    sb: Storyboard,
    *,
    job: JobStore,
    settings: Settings,
    narrations: dict[int, Path] | None = None,
    dialogues: dict[int, Path] | None = None,
) -> Path:
    started = time.perf_counter()
    work = job.dir / "compose"
    work.mkdir(exist_ok=True)
    narrations = narrations or {}
    dialogues = dialogues or {}
    size = _FRAME_SIZES.get((settings.aspect_ratio, settings.video_resolution), (720, 1280))

    seconds = [c.duration_seconds for c in sb.cuts]
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
    for cut, start in zip(sb.cuts, starts):
        src = job.cut_video(cut.index)
        if not src.exists():
            raise VideomakeError(f"컷 {cut.index}의 영상이 없다: {src}")
        video = work / f"{cut.index:02d}.mp4"
        _prepare_video(src, video, seconds=cut.duration_seconds, size=size)
        videos.append(video)

        start_ms = int(start * 1000)
        dubbed = dialogues.get(cut.index) if cut.is_dialogue else None
        if dubbed is not None:
            audios.append((dubbed, start_ms, 0.0))
            voices[cut.index] = dubbed
        elif cut.is_dialogue or settings.veo_audio == "ambient":
            voice = work / f"{cut.index:02d}_veo.wav"
            if _extract_audio(src, voice, seconds=cut.duration_seconds):
                if cut.is_dialogue:
                    gain = 0.0
                    voices[cut.index] = voice
                else:
                    target = (
                        settings.veo_ambient_gain_db
                        if cut.index in under_voice
                        else settings.veo_ambient_solo_gain_db
                    )
                    gain = _level_gain(voice, target)
                audios.append((voice, start_ms, gain))
        narration = narrations.get(cut.index)
        if narration is not None and not cut.is_dialogue:
            audios.append((narration, start_ms + NARRATION_DELAY_MS, 0.0))
        log.info("컷 %d 준비 완료 (%.1fs부터)", cut.index, start)

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
        for k, (_, delay_ms, gain) in enumerate(audios):
            label = f"a{k}"
            filters.append(
                f"[{first_audio + k}:a]aresample={AUDIO_RATE},"
                f"aformat=channel_layouts=stereo,volume={gain}dB,"
                f"adelay={delay_ms}:all=1[{label}]"
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
                        narration_delay=NARRATION_DELAY_MS / 1000)
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
