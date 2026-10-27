"""컷 영상 검사 — 영상 AI가 만든 영상을 받은 직후 확인한다.

영상 AI는 한 번 생성으로 샷 전환까지 만드는데, 지시와 다르게 만드는 일이 있다(B단계 비교에서 관측):
  1) 끝에 0.2초쯤 첫 장면이 다시 튀어나온다 → 그 조각을 바로 앞 프레임 정지로 덮는다(무료).
  2) 샷 수가 계획과 다르다(3샷인데 4샷).
  3) 같은 사람이 둘로 나온다(어깨너머 샷의 앞사람이 상대가 아니라 주인공 복제), 없던 사람이 나온다.
2·3은 다시 만들면 돈이 들어서 자동으로 다시 만들지 않는다. cuts/NN/video_check.json에 남겨
검수 화면·사용자가 그 컷만 다시 만들지 고르게 한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from pathlib import Path

from pydantic import BaseModel

from ..job import JobStore
from ..models import Cut, Storyboard
from ..providers.base import CastCheck, ContinuityProvider, LookProvider, TimedFrame
from .compose import _ffmpeg, _run

log = logging.getLogger(__name__)

# 장면 변화 점수(0~1)가 이보다 크면 샷이 바뀐 것으로 본다. 한 샷 안의 느린 움직임은 0.1 아래다.
SCENE_THRESHOLD = 0.3
# 마지막 전환 뒤 남은 길이가 이보다 짧으면 의도한 샷이 아니라 튀는 조각이다(계획 샷은 1.5초 이상).
TAIL_MAX_SECONDS = 0.6

_PTS = re.compile(r"pts_time:([0-9.]+)")
_DURATION = re.compile(r"Duration: (\d+):(\d+):([0-9.]+)")


class VideoCheck(BaseModel):
    cut_index: int
    scene_cuts: list[float] = []  # 덮은 뒤 남은 샷 전환 시각(초)
    tail_covered_from: float | None = None  # 끝 조각을 정지 화면으로 덮기 시작한 시각
    issues: list[str] = []

    @property
    def needs_rerender(self) -> bool:
        return bool(self.issues)


def scene_cuts(path: Path) -> tuple[list[float], float]:
    """샷 전환 시각들과 영상 길이."""
    proc = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-i", str(path),
         "-vf", f"select='gt(scene,{SCENE_THRESHOLD})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
    )
    times = [float(t) for t in _PTS.findall(proc.stderr)]
    m = _DURATION.search(proc.stderr)
    duration = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0
    return times, duration


def cover_tail_flash(path: Path, cuts: list[float], duration: float) -> float | None:
    """마지막 전환이 끝에서 TAIL_MAX_SECONDS 안이면 그 조각을 바로 앞 프레임 정지로 덮는다.

    길이와 소리는 그대로 둔다(나레이션·편집 시간표가 컷 길이를 기준으로 한다). 덮었으면 시작 시각.
    """
    if not cuts or duration <= 0 or duration - cuts[-1] >= TAIL_MAX_SECONDS:
        return None
    start = cuts[-1]
    # 조각 첫 프레임보다 조금 앞에서 자른다(반올림으로 그 프레임이 남으면 그 프레임이 정지 화면이 된다).
    keep_until = max(start - 0.01, 0.0)
    tmp = path.with_name(path.stem + ".covering.mp4")
    _run([
        _ffmpeg(), "-y", "-i", str(path),
        "-filter_complex",
        f"[0:v]trim=end={keep_until:.3f},setpts=PTS-STARTPTS,"
        f"tpad=stop_mode=clone:stop_duration={duration - keep_until + 0.05:.3f},trim=end={duration:.3f}[v]",
        "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy", str(tmp),
    ])
    tmp.replace(path)
    return start


def _frame_at(path: Path, t: float, dest: Path, *, width: int | None = None) -> Path:
    scale = ["-vf", f"scale={width}:-2"] if width else []
    _run([_ffmpeg(), "-y", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", *scale, str(dest)])
    return dest


def continuity_times(cuts: list[float], duration: float) -> list[tuple[float, int]]:
    """샷마다 시작·가운데·끝 프레임 시각(샷 번호와 함께). 전환 바로 앞뒤를 봐야 물건·손 위치가 바뀐 걸 잡는다."""
    bounds = [0.0, *cuts, duration]
    times = []
    for k, (a, b) in enumerate(zip(bounds, bounds[1:]), 1):
        for t in (a + 0.15, (a + b) / 2, b - 0.15):
            # 짧은 샷에서 같은 샷 프레임이 겹치지 않게만 거른다(전환 바로 앞뒤 프레임은 꼭 남긴다).
            if a < t < b and not (times and times[-1][1] == k and t - times[-1][0] < 0.3):
                times.append((round(t, 2), k))
    return times


def shot_issue(cut: Cut, cuts: list[float]) -> str | None:
    want = len(cut.shots) - 1 if cut.shots else 0
    if len(cuts) == want:
        return None
    return f"샷 전환이 {len(cuts)}번 있다(계획 {want}번)."


async def check_cut_video(
    sb: Storyboard, cut: Cut, path: Path, *, look: LookProvider | None, job: JobStore
) -> VideoCheck:
    """끝 조각을 덮고, 샷 수·사람을 확인해 cuts/NN/video_check.json에 남긴다. 검사 실패는 렌더를 막지 않는다."""
    result = VideoCheck(cut_index=cut.index)
    try:
        cuts, duration = await asyncio.to_thread(scene_cuts, path)
        result.tail_covered_from = await asyncio.to_thread(cover_tail_flash, path, cuts, duration)
        if result.tail_covered_from is not None:
            log.info("컷 %d: 끝 %.2f초부터 튀는 조각을 정지 화면으로 덮었다", cut.index, result.tail_covered_from)
            cuts = cuts[:-1]
        result.scene_cuts = cuts
        if issue := shot_issue(cut, cuts):
            result.issues.append(issue)
        if look is not None:
            result.issues += await _people_issues(sb, cut, path, cuts, duration, look=look, job=job)
        if cuts and isinstance(look, ContinuityProvider):
            result.issues += await _continuity_issues(cut, path, cuts, duration, look=look, job=job)
    except Exception as exc:  # 검사 도구 문제로 이미 돈 낸 영상을 버리지 않는다.
        log.warning("컷 %d 영상 검사 실패(영상은 그대로 쓴다): %s", cut.index, exc)
    if result.issues:
        log.warning("컷 %d 영상 확인 필요: %s", cut.index, " / ".join(result.issues))
    (job.cut_dir(cut.index) / "video_check.json").write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


async def _people_issues(
    sb: Storyboard, cut: Cut, path: Path, cuts: list[float], duration: float,
    *, look: LookProvider, job: JobStore,
) -> list[str]:
    """샷마다 가운데 프레임 한 장을 보고 같은 사람이 둘인지, 없던 사람이 있는지 본다(샷당 약 1원)."""
    people = []
    for m in sb.visible_cast(cut):
        profile = sb.character(m.name)
        people.append(profile.appearance.split(".")[0].strip() if profile else m.name)
    check = CastCheck(people=people)
    bounds = [0.0, *cuts, duration]
    issues = []
    for k, (a, b) in enumerate(zip(bounds, bounds[1:]), 1):
        frame = await asyncio.to_thread(
            _frame_at, path, (a + b) / 2, job.cut_dir(cut.index) / f"check_shot{k}.png"
        )
        seen = await look.look(image=frame, cast=check)
        if seen.duplicate_person:
            issues.append(f"샷 {k}: 같은 사람이 두 번 나온다.")
        if seen.unknown_person:
            issues.append(f"샷 {k}: 계획에 없던 사람이 나온다.")
    return issues


async def _continuity_issues(
    cut: Cut, path: Path, cuts: list[float], duration: float,
    *, look: ContinuityProvider, job: JobStore,
) -> list[str]:
    """샷을 나눈 컷만: 샷마다 시작·가운데·끝 프레임을 한 번에 보여주고 연결 오류를 묻는다(컷당 약 2~3원)."""
    frames = []
    for t, shot in continuity_times(cuts, duration):
        dest = job.cut_dir(cut.index) / f"check_t{t:05.2f}.png"
        frames.append(TimedFrame(time=t, shot=shot, image=await asyncio.to_thread(_frame_at, path, t, dest, width=360)))
    scene = cut.motion_prompt + " " + " ".join(f"Shot {i}: {s.view}" for i, s in enumerate(cut.shots, 1))
    return [f"샷 연결: {p}" for p in await look.continuity(frames=frames, scene=scene)]
