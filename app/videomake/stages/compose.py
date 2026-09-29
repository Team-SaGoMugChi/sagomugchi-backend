"""7. Compositor — ffmpeg stitch + 나레이션 믹싱 + 페이드 → final.mp4

Veo는 오디오 생성을 끌 수 없다(Developer API에 generate_audio가 없다).
따라서 여기서 처리한다:
  - veo_audio="mute"   : Veo 오디오를 버리고 나레이션만 남긴다 (기본)
  - veo_audio="ambient": Veo 오디오를 크게 감쇠해 앰비언트로 깔고 나레이션을 얹는다
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from ..config import Settings
from ..errors import VideomakeError
from ..job import JobStore
from ..models import Stage, Storyboard

log = logging.getLogger(__name__)

NARRATION_DELAY_MS = 400  # 컷이 시작하고 잠깐 뒤에 목소리가 들어오는 편이 자연스럽다
AUDIO_RATE = 48_000


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


def _build_cut(
    *,
    video_in: Path,
    narration: Path | None,
    dest: Path,
    duration: int,
    settings: Settings,
    keep_source_audio: bool = False,
) -> None:
    """컷 하나의 최종 오디오를 확정한다. 이후 concat이 재인코딩 없이 붙도록
    모든 컷을 동일한 코덱/파라미터로 맞춘다."""
    args = [_ffmpeg(), "-y", "-i", str(video_in)]
    if narration is not None:
        args += ["-i", str(narration)]

    nar_chain = (
        f"adelay={NARRATION_DELAY_MS}|{NARRATION_DELAY_MS},"
        f"aresample={AUDIO_RATE},apad"
    )
    if keep_source_audio:
        # 대사 컷. Veo가 만든 인물 목소리가 그 자체로 이 컷의 오디오다.
        filt = f"[0:a]aresample={AUDIO_RATE},apad[a]"
    elif narration is None:
        # 나레이션이 없는 컷도 무음 트랙을 넣어야 concat에서 스트림 구성이 어긋나지 않는다.
        args += [
            "-f", "lavfi", "-t", str(duration),
            "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo",
        ]
        filt = None
    elif settings.veo_audio == "mute":
        filt = f"[1:a]{nar_chain}[a]"
    else:
        filt = (
            f"[0:a]volume={settings.veo_ambient_gain_db}dB,aresample={AUDIO_RATE}[amb];"
            f"[1:a]{nar_chain}[nar];"
            "[amb][nar]amix=inputs=2:duration=first:normalize=0[a]"
        )

    if filt is not None:
        args += ["-filter_complex", filt, "-map", "0:v:0", "-map", "[a]"]
    else:
        args += ["-map", "0:v:0", "-map", "1:a:0"]

    args += [
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", "2",
        "-movflags", "+faststart",
        str(dest),
    ]
    _run(args)


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

    staged: list[Path] = []
    for cut in sb.cuts:
        src = job.cut_video(cut.index)
        if not src.exists():
            raise VideomakeError(f"컷 {cut.index}의 영상이 없다: {src}")
        out = work / f"{cut.index:02d}.mp4"
        _build_cut(
            video_in=src,
            narration=narrations.get(cut.index),
            dest=out,
            duration=cut.duration_seconds,
            settings=settings,
            keep_source_audio=cut.is_dialogue,
        )
        staged.append(out)
        log.info("컷 %d 믹싱 완료", cut.index)

    concat_list = work / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.name}'" for p in staged) + "\n", encoding="utf-8"
    )
    stitched = work / "stitched.mp4"
    _run([
        _ffmpeg(), "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", str(stitched),
    ])

    total = sb.total_seconds
    fade = settings.fade_seconds
    out_start = max(total - fade, 0)
    _run([
        _ffmpeg(), "-y", "-i", str(stitched),
        "-vf", f"fade=t=in:st=0:d={fade},fade=t=out:st={out_start}:d={fade}",
        "-af", f"afade=t=in:st=0:d={fade},afade=t=out:st={out_start}:d={fade}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(job.final_path),
    ])

    job.record_stage(
        Stage.COMPOSE,
        elapsed_s=time.perf_counter() - started,
        path=str(job.final_path),
        duration_s=total,
    )
    log.info("final.mp4 완성 — %ds", total)
    return job.final_path
