"""오케스트레이션.

이 모듈이 OddO FastAPI의 서비스 레이어가 된다. 모든 함수는 순수 async이고
provider / JobStore / Settings를 주입받는다. CLI는 이 위에 얹힌 얇은 껍데기다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from .config import Settings, get_settings
from .cost import enforce_budget, estimate_full_job
from .errors import VideoBlocked
from .job import JobStore
from .models import CameraDistance, CostEstimate, DiaryInput, Storyboard
from .prompts import PromptLibrary, get_prompts
from .providers.registry import Providers
from .stages.character_sheet import build_character_sheet
from .stages.compose import compose
from .stages.cut_images import generate_cut_images
from .stages.dialogue_voice import dub_dialogue
from .stages.edit_plan import load_plan, make_music, plan_edit
from .stages.film_team import plan_with_team
from .stages.narration import synthesize_narrations
from .stages.narration_flow import polish_narration
from .stages.reference_sheets import build_reference_sheets
from .stages.review import build_review
from .stages.storyboard import plan_storyboard
from .stages.thumbnail import build_thumbnail
from .stages.video_render import render_cut_videos

log = logging.getLogger(__name__)


# 안전 필터 거절 시 다시 그리는 횟수와 넓혀 갈 구도.
BLOCK_REDRAWS = 2
WIDER: dict[str, CameraDistance] = {"medium": "full", "full": "wide", "wide": "wide"}
WIDER_NOTE = "Seen from farther away: everyone is visible from head to toe and faces are small in the frame."


class Pipeline:
    def __init__(
        self,
        *,
        providers: Providers,
        job: JobStore,
        settings: Settings | None = None,
        prompts: PromptLibrary | None = None,
    ) -> None:
        self.p = providers
        self.job = job
        self.settings = settings or get_settings()
        self.prompts = prompts or get_prompts()

    # --- 1. 스토리보드 -------------------------------------------------------
    async def plan(self, diary: DiaryInput, *, force: bool = False) -> Storyboard:
        if self.job.storyboard_path.exists() and not force:
            log.info("스토리보드 캐시 재사용")
            return self.job.load_storyboard()
        self.job.input_path.write_text(
            diary.model_dump_json(indent=2), encoding="utf-8"
        )
        planner = plan_with_team if self.settings.planner == "team" else plan_storyboard
        sb = await planner(
            diary,
            llm=self.p.llm,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
        )
        if self.settings.narration_polish:
            sb = await polish_narration(sb, diary, llm=self.p.llm, job=self.job)
        return sb

    # --- 2~3. 캐릭터 시트 + 컷 이미지 ------------------------------------------
    async def build_images(
        self,
        sb: Storyboard,
        *,
        only: set[int] | None = None,
        force: bool = False,
    ) -> dict[int, Path]:
        sheet = await build_character_sheet(
            sb,
            image=self.p.image,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
            force=force and only is None,
        )
        # 조연·장소 시트. 컷 일부만 다시 그릴 때는 기존 시트를 그대로 쓴다.
        character_sheets, location_sheets = await build_reference_sheets(
            sb,
            image=self.p.image,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
            force=force and only is None,
        )
        images = await generate_cut_images(
            sb,
            sheet=sheet,
            character_sheets=character_sheets,
            location_sheets=location_sheets,
            image=self.p.image,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
            only=only,
            force=force,
            look=self.p.look,
        )
        build_review(sb, self.job)
        return images

    # --- 4. 승인 게이트 -------------------------------------------------------
    def review(self, sb: Storyboard) -> Path:
        return build_review(sb, self.job)

    def approve(self, sb: Storyboard, indices: set[int] | None = None) -> set[int]:
        target = indices if indices is not None else {c.index for c in sb.cuts}
        missing = [i for i in sorted(target) if not self.job.cut_image(i).exists()]
        if missing:
            raise FileNotFoundError(f"컷 {missing}의 이미지가 아직 없다")
        self.job.approve(target)
        return self.job.approved_cuts()

    # --- 비용 -----------------------------------------------------------------
    def estimate(self, sb: Storyboard, *, only: set[int] | None = None) -> CostEstimate:
        cuts = [c for c in sb.cuts if only is None or c.index in only]
        return estimate_full_job(
            image_model=self.settings.image_model,
            image_size=self.settings.image_size,
            video_model=self.settings.video_model,
            resolution=self.settings.video_resolution,
            cut_seconds=[c.duration_seconds for c in cuts],
        )

    # --- 5~7. 렌더 → 나레이션 → 합성 --------------------------------------------
    async def render(
        self,
        sb: Storyboard,
        *,
        only: set[int] | None = None,
        force: bool = False,
        confirm: Callable[[CostEstimate, Decimal], bool] | None = None,
        redraw_blocked: bool = False,
    ) -> dict[int, Path]:
        """redraw_blocked: 안전 필터에 거절된 컷을 넓은 구도로 다시 그려 자동 승인·재시도한다.
        사람이 그림을 검수하는 흐름에서는 켜지 않는다(승인 안 한 그림으로 영상을 만들게 된다)."""
        estimate = self.estimate(sb, only=only)
        log.info("예상 비용 $%.2f (상한 $%.2f)", estimate.total_usd, self.settings.max_cost_usd)
        enforce_budget(estimate, self.settings.max_cost_usd, confirm=confirm)
        for attempt in range(BLOCK_REDRAWS + 1):
            try:
                return await render_cut_videos(
                    sb,
                    video=self.p.video,
                    prompts=self.prompts,
                    settings=self.settings,
                    job=self.job,
                    only=only,
                    # 다시 시도할 때 force를 쓰면 이미 받은 컷까지 다시 과금된다.
                    force=force and attempt == 0,
                    look=self.p.look,
                    listen=self.p.listen if self.settings.dialogue_voice == "auto" else None,
                )
            except VideoBlocked as exc:
                if not redraw_blocked or attempt == BLOCK_REDRAWS:
                    raise
                log.warning("컷 %s 안전 필터 거절 — 넓은 구도로 다시 그린다(%d/%d)", sorted(exc.cuts), attempt + 1, BLOCK_REDRAWS)
                await self._redraw_wider(sb, exc.cuts)
        raise AssertionError("unreachable")

    async def _redraw_wider(self, sb: Storyboard, cuts: set[int]) -> None:
        """얼굴이 크게 나온 구도가 주로 거절됐다(2026-10 실측: 허리 위 → 전신으로 통과). 그림값만 든다."""
        for index in cuts:
            cut = sb.cut(index)
            cut.camera_distance = WIDER[cut.camera_distance]
            if WIDER_NOTE not in cut.image_prompt:
                cut.image_prompt = f"{cut.image_prompt} {WIDER_NOTE}"
        self.job.save_storyboard(sb)
        await self.build_images(sb, only=cuts, force=True)
        self.approve(sb, cuts)

    async def narrate(
        self, sb: Storyboard, *, only: set[int] | None = None, force: bool = False
    ) -> dict[int, Path]:
        return await synthesize_narrations(
            sb,
            tts=self.p.narration_tts or self.p.tts,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
            only=only,
            force=force,
        )

    async def dub(self, sb: Storyboard, *, force: bool = False) -> dict[int, Path]:
        return await dub_dialogue(
            sb,
            tts=self.p.tts,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
            force=force,
            listen=self.p.listen,
        )

    # --- 한 번에 --------------------------------------------------------------
    async def run_to_gate(
        self, diary: DiaryInput, *, force: bool = False
    ) -> Storyboard:
        """일기 → 스토리보드 → 캐릭터 시트 → 컷 이미지. 승인 게이트 직전에서 멈춘다.

        여기까지가 싼 구간이다(수십 센트). 이 다음부터 컷당 $0.80이므로
        사람이 눈으로 확인하기 전에는 넘어가지 않는다.
        """
        sb = await self.plan(diary, force=force)
        await self.build_images(sb, force=force)
        return sb

    async def finish(
        self,
        sb: Storyboard,
        *,
        confirm: Callable[[CostEstimate, Decimal], bool] | None = None,
        force: bool = False,
        redraw_blocked: bool = False,
    ) -> Path:
        """승인된 컷 → 영상 → 나레이션 → final.mp4. 비싼 구간.

        대표 장면 썸네일은 영상 렌더와 동시에 그린다(기다리는 시간이 늘지 않는다).
        썸네일이 실패해도 영상은 완성한다 — 앱은 썸네일 없이도 영상을 보여준다.
        """
        thumbnail = asyncio.create_task(self.thumbnail(sb, force=force))
        try:
            await self.render(sb, force=force, confirm=confirm, redraw_blocked=redraw_blocked)
        except BaseException:
            thumbnail.cancel()
            raise
        _, _, music = await asyncio.gather(
            self.narrate(sb, force=force), self.dub(sb, force=force), self.edit(sb, force=force)
        )
        final = self.compose(sb, music=music)
        try:
            await thumbnail
        except Exception:
            log.exception("썸네일 생성 실패 — 영상은 그대로 완성")
        return final

    async def thumbnail(self, sb: Storyboard, *, force: bool = False) -> Path:
        """대표 장면을 가로(16:9)로 한 장 그린다(stages/thumbnail.py)."""
        primary = None
        if self.job.input_path.exists():
            diary = DiaryInput.model_validate_json(self.job.input_path.read_text(encoding="utf-8"))
            primary = diary.emotion.get("primary")
        character_sheets, location_sheets = await build_reference_sheets(
            sb, image=self.p.image, prompts=self.prompts, settings=self.settings, job=self.job
        )
        return await build_thumbnail(
            sb,
            primary_emotion=primary,
            sheets={sb.protagonist.name: self.job.character_sheet_path, **character_sheets},
            location_sheets=location_sheets,
            image=self.p.image,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
            force=force,
        )

    async def edit(self, sb: Storyboard, *, force: bool = False) -> dict[int, Path]:
        """편집 계획(끝까지 보여줄 컷·배경음악 구간)을 정하고 음악을 만든다(stages/edit_plan.py)."""
        plan = await plan_edit(
            sb, llm=self.p.llm, prompts=self.prompts, settings=self.settings, job=self.job, force=force
        )
        return await make_music(plan, music=self.p.music, job=self.job, force=force)

    def compose(
        self,
        sb: Storyboard,
        narrations: dict[int, Path] | None = None,
        music: dict[int, Path] | None = None,
    ) -> Path:
        if narrations is None:
            narrations = {
                c.index: self.job.cut_narration(c.index)
                for c in sb.cuts
                if self.job.cut_narration(c.index).exists()
            }
        dialogues = {
            c.index: self.job.cut_dialogue(c.index)
            for c in sb.cuts
            if c.is_dialogue and self.job.cut_dialogue(c.index).exists()
        }
        plan = load_plan(self.job)
        if music is None and plan is not None:
            music = {
                k: p for k in range(len(plan.music))
                if (p := self.job.dir / "music" / f"cue{k}.wav").exists()
            }
        return compose(
            sb, job=self.job, settings=self.settings, narrations=narrations, dialogues=dialogues,
            plan=plan.checked(sb) if plan else None, music=music,
        )
