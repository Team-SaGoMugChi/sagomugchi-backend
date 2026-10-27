"""5. VideoRenderer — 승인된 컷 이미지를 first frame으로 Veo image-to-video 호출.

비동기 병렬 제출 + 단일 폴링 루프. 진입 즉시 승인 여부를 강제 확인한다.
승인 없이 Veo를 호출하는 경로가 코드상 존재해서는 안 된다 (컷당 약 $0.80).
"""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from pathlib import Path

from ..config import Settings
from ..errors import ProviderError, RenderTimeout
from ..job import JobStore
from ..models import Stage, Storyboard, VideoHandle
from ..prompts import PromptLibrary
from ..providers.base import LookProvider, VideoProvider
from .cut_images import mood_subject, solo_listener_side, voice_off_screen
from .video_check import check_cut_video

log = logging.getLogger(__name__)


async def render_cut_videos(
    sb: Storyboard,
    *,
    video: VideoProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    only: set[int] | None = None,
    force: bool = False,
    look: LookProvider | None = None,
) -> dict[int, Path]:
    """look: 받은 영상의 샷마다 같은 사람이 둘인지·없던 사람이 있는지 본다(없으면 샷 수·끝 조각만 검사)."""
    targets = [c for c in sb.cuts if only is None or c.index in only]
    pending = [c for c in targets if force or not job.cut_video(c.index).exists()]
    cached = {
        c.index: job.cut_video(c.index) for c in targets if c not in pending
    }
    for idx in cached:
        log.info("컷 %d 영상 캐시 재사용", idx)
    if not pending:
        return cached

    # --- 승인 게이트. 여기를 통과하지 못하면 API를 부르지 않는다. ---
    job.assert_approved({c.index for c in pending})

    for cut in pending:
        if not job.cut_image(cut.index).exists():
            raise ProviderError(f"컷 {cut.index}의 시작 프레임 이미지가 없다")

    started = time.perf_counter()
    sem = asyncio.Semaphore(settings.video_concurrency)

    async def submit(cut) -> VideoHandle:
        async with sem:
            # 대사 컷은 화자마다 목소리 서술을 붙여야 전원이 같은 목소리로
            # 말하지 않는다. 또 Veo는 이름만으로 화면 속 누가 그 사람인지 모른다 —
            # 화면 위치와 외모로 가리켜야 대사가 다른 사람 입에서 나오지 않는다.
            # 화면에 없는 화자(전화 속 목소리 등)는 화면 밖 목소리로 따로 알린다.
            positions = {m.name: m.position for m in sb.visible_cast(cut)}
            # 화면 밖 목소리만 있는 컷은 말소리 없이 "듣는" 장면으로 만든다(voice_off_screen).
            listening = voice_off_screen(sb, cut)
            speaks = cut.is_dialogue and not listening
            lines = []
            for line in cut.dialogue if speaks else []:
                profile = sb.character(line.speaker)
                look = (profile.appearance.split(".")[0].strip() if profile else "")
                lines.append({
                    "speaker": line.speaker,
                    "text": line.text,
                    "voice": getattr(profile, "voice", ""),
                    "position": positions.get(line.speaker),
                    "look": look,
                })
            motion = prompts.render(
                "motion.j2",
                motion_prompt=cut.motion_prompt,
                shots=cut.shots,
                duration=cut.duration_seconds,
                outfits=[
                    {"look": p.appearance, "position": m.position}
                    for m in sb.visible_cast(cut)
                    if (p := sb.character(m.name))
                ] if cut.shots else [],
                # 이 컷에 나오는 사람 명단. 영상 AI가 같은 사람을 둘로 만들거나 없던 사람을 넣지 않게 한다.
                people=[
                    (p.appearance.split(".")[0].strip() if (p := sb.character(m.name)) else m.name)
                    for m in sb.visible_cast(cut)
                ],
                dialogue=lines,
                solo_side=solo_listener_side(sb, cut, sb.visible_cast(cut)),
                ambient=settings.veo_audio == "ambient",
                listening=listening,
                mood_line=prompts.render(
                    "mood.j2", mood=cut.mood, name=mood_subject(sb, cut), part="motion"
                ),
            )
            handle = await video.submit(
                cut_index=cut.index,
                motion_prompt=motion,
                first_frame=job.cut_image(cut.index),
                negative_prompt=(
                    prompts.video_negative_prompt_dialogue
                    if speaks
                    else prompts.video_negative_prompt
                ),
                aspect_ratio=settings.aspect_ratio,
                resolution=settings.video_resolution,
                duration_seconds=cut.duration_seconds,
                # ambient면 모든 컷에서 장면 소리(발소리·거리·그릇 소리)를 만든다. 소리 포함은 더 비싸다.
                generate_audio=speaks or settings.veo_audio == "ambient",
                speaking=speaks,
            )
        job.cut_handle(cut.index).write_text(
            handle.model_dump_json(indent=2), encoding="utf-8"
        )
        log.info("컷 %d 제출됨: %s", cut.index, handle.operation_name)
        return handle

    # 이미 제출된 컷은 절대 다시 제출하지 않는다. 재제출하면 그만큼 다시 과금된다.
    handles: list[VideoHandle] = []
    to_submit = []
    for cut in pending:
        hp = job.cut_handle(cut.index)
        if hp.exists() and not force:
            h = VideoHandle.model_validate_json(hp.read_text(encoding="utf-8"))
            log.info("컷 %d: 진행 중인 작업을 이어받는다 (%s)", cut.index, h.operation_name)
            handles.append(h)
        else:
            to_submit.append(cut)

    errors: list[str] = []
    # 일부 제출이 실패해도 성공한 것들은 끝까지 회수한다.
    submitted = await asyncio.gather(
        *(submit(c) for c in to_submit), return_exceptions=True
    )
    for cut, outcome in zip(to_submit, submitted):
        if isinstance(outcome, BaseException):
            errors.append(f"컷 {cut.index} 제출 실패: {outcome}")
            log.error("컷 %d 제출 실패: %s", cut.index, outcome)
        else:
            handles.append(outcome)

    results = dict(cached)
    remaining = {h.cut_index: h for h in handles}
    deadline = time.monotonic() + settings.poll_timeout_seconds

    while remaining:
        if time.monotonic() > deadline:
            raise RenderTimeout(
                f"컷 {sorted(remaining)}이 {settings.poll_timeout_seconds:.0f}초 안에 "
                "완료되지 않았다. 핸들은 job 디렉터리에 저장되어 있다."
            )
        await asyncio.sleep(settings.poll_interval_seconds)
        statuses = await asyncio.gather(
            *(video.poll(h) for h in remaining.values())
        )
        for handle, status in zip(list(remaining.values()), statuses):
            if not status.done:
                continue
            remaining.pop(handle.cut_index)
            if status.failed:
                errors.append(f"컷 {handle.cut_index}: {status.error}")
                log.error("컷 %d 실패: %s", handle.cut_index, status.error)
                # 실패한 작업의 핸들을 지운다. 남겨 두면 다시 시도해도 실패한 작업만
                # 다시 조회해 영원히 실패한다(서버 과부하 code 8에서 관측). 실패한 작업은 과금되지 않는다.
                job.cut_handle(handle.cut_index).unlink(missing_ok=True)
                continue
            dest = job.cut_video(handle.cut_index)
            try:
                fetched = await video.fetch(handle, dest)
            except ProviderError as exc:
                # 작업은 끝났는데 영상이 없다(안전 필터 등). 핸들을 남기면 재시도가 같은 결과만 다시 읽는다.
                errors.append(str(exc))
                log.error("컷 %d 실패: %s", handle.cut_index, exc)
                job.cut_handle(handle.cut_index).unlink(missing_ok=True)
                continue
            cut = sb.cut(handle.cut_index)
            # provider가 실제 차감액을 알려주면(evolink) 그것을, 아니면 단가 × 길이를 기록한다.
            cost = fetched.cost_usd or (
                video.price_per_second(settings.video_resolution) * cut.duration_seconds
            )
            job.record_cost(f"cut{handle.cut_index}_video", Decimal(cost))
            results[handle.cut_index] = dest
            await check_cut_video(sb, cut, dest, look=look, job=job)
            log.info(
                "컷 %d 완료 — %s ($%.2f)", handle.cut_index, dest.name, cost
            )
        log.info("대기 중인 컷: %s", sorted(remaining) or "없음")

    job.record_stage(
        Stage.VIDEOS,
        elapsed_s=time.perf_counter() - started,
        cuts=sorted(results),
        errors=errors,
    )
    if errors:
        raise ProviderError(
            "일부 컷 렌더 실패 (성공한 컷은 캐시되어 재렌더되지 않는다):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
    return results
