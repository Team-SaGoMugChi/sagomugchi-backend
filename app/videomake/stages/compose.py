"""7. Compositor — 컷 크로스페이드 + 나레이션·대사를 한 시간축에 배치 + 페이드 → final.mp4

컷은 CROSSFADE_SECONDS만큼 겹쳐 넘긴다(짧은 컷이 툭툭 끊겨 보이지 않게).
소리는 컷마다 따로 붙이지 않고 영상 전체 시간축에 놓는다:
  - 나레이션: 그 컷이 시작하고 NARRATION_DELAY_MS 뒤. 뒤따르는 무음 컷까지 이어서 깔릴 수 있다
    (글자 수는 스토리보드 단계에서 그 구간 안에 들어가게 막는다).
  - 대사 컷: Veo가 만든 인물 목소리를 그 컷 구간에.
  - veo_audio="ambient"면 Veo 오디오를 크게 감쇠해 모든 컷 아래에 깐다. 기본 "mute"는 버린다.

Veo는 오디오 생성을 끌 수 없다(Developer API에 generate_audio가 없다). 그래서 여기서 고른다.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from ..config import CROSSFADE_SECONDS, Settings
from ..errors import VideomakeError
from ..job import JobStore
from ..models import Stage, Storyboard

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
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
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
        capture_output=True, text=True, check=False,
    )
    return proc.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def compose(
    sb: Storyboard,
    *,
    job: JobStore,
    settings: Settings,
    narrations: dict[int, Path] | None = None,
) -> Path:
    started = time.perf_counter()
    work = job.dir / "compose"
    work.mkdir(exist_ok=True)
    narrations = narrations or {}
    size = _FRAME_SIZES.get((settings.aspect_ratio, settings.video_resolution), (720, 1280))

    seconds = [c.duration_seconds for c in sb.cuts]
    starts = cut_starts(seconds)
    total = round(starts[-1] + seconds[-1], 3) if seconds else 0.0
    x = CROSSFADE_SECONDS

    videos: list[Path] = []
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
        if cut.is_dialogue or settings.veo_audio == "ambient":
            voice = work / f"{cut.index:02d}_veo.wav"
            if _extract_audio(src, voice, seconds=cut.duration_seconds):
                gain = 0.0 if cut.is_dialogue else settings.veo_ambient_gain_db
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
        f"[{mixed}]apad,atrim=0:{total},"
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

    job.record_stage(
        Stage.COMPOSE,
        elapsed_s=time.perf_counter() - started,
        path=str(job.final_path),
        duration_s=total,
    )
    log.info("final.mp4 완성 — %.1fs", total)
    return job.final_path
