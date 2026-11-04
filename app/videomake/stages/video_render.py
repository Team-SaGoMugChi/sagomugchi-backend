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
from ..errors import ProviderError, RenderTimeout, VideoBlocked
from ..job import JobStore
from ..models import Stage, Storyboard, VideoHandle
from ..prompts import PromptLibrary
from ..providers.base import ListenProvider, LookProvider, VideoProvider, is_rate_limited
from .cut_images import mood_subject, solo_listener_side, voice_off_screen
from .dialogue_voice import _load_mono, judge_veo_voice, speech_segments
from .video_check import check_cut_video

log = logging.getLogger(__name__)

RESUBMIT_TRIES = 10  # 동시 작업 한도로 다시 제출하는 최대 횟수(컷마다)
# 진행 상태 조회 한 번의 제한 시간(초). 응답 없는 조회 하나가 끝나지 않아 렌더 전체가 3시간 멈췄다
# (2026-11, 네트워크가 잠깐 끊긴 뒤 — Veo 쪽 작업은 이미 끝나 있었다). 넘기면 이번 조회는 "아직"으로 본다.
CALL_TIMEOUT_SECONDS = 60


POLL_FAILURES_MAX = 5  # 조회가 이만큼 연달아 안 되면 그 작업을 버린다(과금되지 않은 작업이다)


async def _poll(video: VideoProvider, handle: VideoHandle) -> VideoStatus | None:
    """진행 상태 조회. 제한 시간을 넘기거나 오류면 None — 다음 조회 때 다시 묻는다."""
    try:
        return await asyncio.wait_for(video.poll(handle), CALL_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, ProviderError) as exc:
        log.warning("컷 %d 진행 상태를 조회하지 못했다(다시 묻는다): %s", handle.cut_index, exc)
        return None
INTRUDER_REDO = 1  # 화면 끝에 낯선 사람이 너무 일찍 들어온 컷을 다시 만드는 횟수(컷마다, 그만큼 과금)


def intruder_too_early(cut, video: Path, clean_until: float | None) -> bool:
    """화면 끝에 사람이 들어오기 전까지만으로는 컷을 못 쓰는가.

    대사 컷은 말이 끝나기 전, 다른 컷은 컷 길이의 60% 전에 들어오면 잘라 낼 수 없다(2026-11 강의실 컷 3:
    교수님이 말하는 도중 4초에 남자 뒷모습)."""
    # 첫 장면부터 보이면 그림에 이미 그려진 것이다 — 영상을 다시 만들어도 같다(그림 검사가 막아야 한다).
    if clean_until is None or clean_until <= 0.0:
        return False
    if cut.is_dialogue:
        segments = speech_segments(_load_mono(video, cut.duration_seconds))
        return bool(segments) and clean_until < segments[-1][1]
    return clean_until < cut.duration_seconds * 0.6

# 안전 필터 거절 문구. Veo: "the input image violates Vertex AI's usage guidelines"(code 3, 과금 없음),
# 영상 없이 끝난 작업: fetch의 "안전 필터 사유". 서버 과부하 같은 실패와 구별해 그림을 바꿔 다시 시도한다.
_BLOCK_WORDS = ("usage guidelines", "안전 필터")


# 배경 손님이 있어야 하는 장소에서는 이 말들을 빼야 Veo가 손님을 지우지 않는다.
_CROWD_TERMS = ("bystanders", "crowd", "extra person", "extra people")


def _without_crowd_terms(negative: str) -> str:
    kept = [t for t in negative.split(", ") if t.strip() not in _CROWD_TERMS]
    return ", ".join(kept)


def _is_blocked(error: object) -> bool:
    return any(word in str(error) for word in _BLOCK_WORDS)


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
    listen: ListenProvider | None = None,
) -> dict[int, Path]:
    """look: 받은 영상의 샷마다 같은 사람이 둘인지·없던 사람이 있는지 본다(없으면 샷 수·끝 조각만 검사).
    listen: 대사 컷의 Veo 목소리를 들어 보고, 대본과 다르거나·말이 잘렸거나·성별이 다르면 그 컷을 다시 만든다
    (settings.veo_voice_redo번까지). TTS로 바꾸지 않는다 — TTS 목소리는 입 모양과 어울리지 않았다."""
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
            place = sb.location(cut.location)
            crowd = place.background_people if place else ""
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
                background_people=crowd,
                solo_side=solo_listener_side(sb, cut, sb.visible_cast(cut)),
                ambient=settings.veo_audio == "ambient",
                listening=listening,
                mood_line=prompts.render(
                    "mood.j2", mood=cut.mood, name=mood_subject(sb, cut), part="motion"
                ),
            )
            negative = (
                prompts.video_negative_prompt_dialogue if speaks else prompts.video_negative_prompt
            )
            if crowd:
                negative = _without_crowd_terms(negative)
            handle = await video.submit(
                cut_index=cut.index,
                motion_prompt=motion,
                first_frame=job.cut_image(cut.index),
                negative_prompt=negative,
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
    blocked: set[int] = set()
    # 일부 제출이 실패해도 성공한 것들은 끝까지 회수한다.
    submitted = await asyncio.gather(
        *(submit(c) for c in to_submit), return_exceptions=True
    )
    # 동시 작업 한도(429)로 제출하지 못한 컷은 앞 컷이 끝나 자리가 나면 다시 낸다. 컷 8개를 한꺼번에 내면
    # 마지막 컷이 한도에 걸려 영상 전체가 실패했다(2026-11 카페 일기, Veo 동시 요청 한도).
    waiting: list = []
    tries: dict[int, int] = {}
    redone: dict[int, int] = {}
    poll_failures: dict[int, int] = {}
    voice_redone: dict[int, int] = {}
    for cut, outcome in zip(to_submit, submitted):
        if isinstance(outcome, BaseException) and is_rate_limited(outcome):
            log.warning("컷 %d: 동시 작업 한도 — 앞 컷이 끝나면 다시 제출한다", cut.index)
            waiting.append(cut)
        elif isinstance(outcome, BaseException):
            errors.append(f"컷 {cut.index} 제출 실패: {outcome}")
            log.error("컷 %d 제출 실패: %s", cut.index, outcome)
        else:
            handles.append(outcome)

    results = dict(cached)
    remaining = {h.cut_index: h for h in handles}
    deadline = time.monotonic() + settings.poll_timeout_seconds

    while remaining or waiting:
        if time.monotonic() > deadline:
            raise RenderTimeout(
                f"컷 {sorted(remaining) + [c.index for c in waiting]}이 {settings.poll_timeout_seconds:.0f}초 안에 "
                "완료되지 않았다. 핸들은 job 디렉터리에 저장되어 있다."
            )
        await asyncio.sleep(settings.poll_interval_seconds)
        statuses = await asyncio.gather(*(_poll(video, h) for h in remaining.values()))
        for handle, status in zip(list(remaining.values()), statuses):
            if status is None:
                # 조회가 계속 안 되는 작업(만료·삭제 등)은 버리고 다음 시도에 새로 낸다.
                poll_failures[handle.cut_index] = poll_failures.get(handle.cut_index, 0) + 1
                if poll_failures[handle.cut_index] >= POLL_FAILURES_MAX:
                    remaining.pop(handle.cut_index)
                    errors.append(f"컷 {handle.cut_index}: 진행 상태를 계속 조회하지 못했다")
                    job.cut_handle(handle.cut_index).unlink(missing_ok=True)
                continue
            poll_failures.pop(handle.cut_index, None)
            if not status.done:
                continue
            remaining.pop(handle.cut_index)
            if status.failed:
                errors.append(f"컷 {handle.cut_index}: {status.error}")
                log.error("컷 %d 실패: %s", handle.cut_index, status.error)
                if _is_blocked(status.error):
                    blocked.add(handle.cut_index)
                # 실패한 작업의 핸들을 지운다. 남겨 두면 다시 시도해도 실패한 작업만
                # 다시 조회해 영원히 실패한다(서버 과부하 code 8에서 관측). 실패한 작업은 과금되지 않는다.
                job.cut_handle(handle.cut_index).unlink(missing_ok=True)
                continue
            dest = job.cut_video(handle.cut_index)
            try:
                fetched = await asyncio.wait_for(video.fetch(handle, dest), CALL_TIMEOUT_SECONDS * 4)
            except asyncio.TimeoutError:
                log.warning("컷 %d 영상 내려받기가 멈춰 다음에 다시 받는다", handle.cut_index)
                remaining[handle.cut_index] = handle
                continue
            except ProviderError as exc:
                # 작업은 끝났는데 영상이 없다(안전 필터 등). 핸들을 남기면 재시도가 같은 결과만 다시 읽는다.
                errors.append(str(exc))
                log.error("컷 %d 실패: %s", handle.cut_index, exc)
                if _is_blocked(exc):
                    blocked.add(handle.cut_index)
                job.cut_handle(handle.cut_index).unlink(missing_ok=True)
                continue
            cut = sb.cut(handle.cut_index)
            # provider가 실제 차감액을 알려주면(evolink) 그것을, 아니면 단가 × 길이를 기록한다.
            cost = fetched.cost_usd or (
                video.price_per_second(settings.video_resolution) * cut.duration_seconds
            )
            job.record_cost(f"cut{handle.cut_index}_video", Decimal(cost))
            results[handle.cut_index] = dest
            check = await check_cut_video(sb, cut, dest, look=look, job=job)
            if listen is not None and cut.is_dialogue and voice_redone.get(cut.index, 0) < settings.veo_voice_redo:
                verdict = await judge_veo_voice(sb, cut, video=dest, listen=listen, job=job)
                if verdict.get("retry"):
                    voice_redone[cut.index] = voice_redone.get(cut.index, 0) + 1
                    log.warning("컷 %d 대사가 틀려 영상을 다시 만든다(%d/%d): %s", cut.index,
                                voice_redone[cut.index], settings.veo_voice_redo, verdict["reason"])
                    results.pop(cut.index, None)
                    dest.unlink(missing_ok=True)
                    job.cut_handle(cut.index).unlink(missing_ok=True)
                    waiting.append(cut)
                    continue
            if intruder_too_early(cut, dest, check.clean_until) and redone.get(cut.index, 0) < INTRUDER_REDO:
                # 대사·화면이 끝나기 전에 화면 끝에 낯선 사람이 들어왔다 — 잘라 낼 수 없어 한 번 다시 만든다.
                redone[cut.index] = redone.get(cut.index, 0) + 1
                log.warning("컷 %d: %.1f초에 화면 끝에 사람이 들어와 다시 만든다", cut.index, check.clean_until)
                results.pop(cut.index, None)
                dest.unlink(missing_ok=True)
                job.cut_handle(cut.index).unlink(missing_ok=True)
                waiting.append(cut)
                continue
            log.info(
                "컷 %d 완료 — %s ($%.2f)", handle.cut_index, dest.name, cost
            )
        freed = len(remaining) < len(statuses)
        if waiting and (freed or not remaining):
            cut = waiting.pop(0)
            try:
                remaining[cut.index] = await submit(cut)
            except Exception as exc:
                tries[cut.index] = tries.get(cut.index, 0) + 1
                if is_rate_limited(exc) and tries[cut.index] < RESUBMIT_TRIES:
                    waiting.insert(0, cut)
                else:
                    errors.append(f"컷 {cut.index} 제출 실패: {exc}")
                    log.error("컷 %d 제출 실패: %s", cut.index, exc)
        log.info("대기 중인 컷: %s", sorted(remaining) or "없음")

    job.record_stage(
        Stage.VIDEOS,
        elapsed_s=time.perf_counter() - started,
        cuts=sorted(results),
        errors=errors,
    )
    if errors:
        message = "일부 컷 렌더 실패 (성공한 컷은 캐시되어 재렌더되지 않는다):\n" + "\n".join(f"  - {e}" for e in errors)
        if blocked:
            raise VideoBlocked(message, cuts=blocked)
        raise ProviderError(message)
    return results
