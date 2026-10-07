"""오케스트레이션.

이 모듈이 OddO FastAPI의 서비스 레이어가 된다. 모든 함수는 순수 async이고
provider / JobStore / Settings를 주입받는다. CLI는 이 위에 얹힌 얇은 껍데기다.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from .config import Settings, get_settings
from .cost import enforce_budget, estimate_full_job
from .job import JobStore
from .models import CostEstimate, DiaryInput, Storyboard
from .prompts import PromptLibrary, get_prompts
from .providers.registry import Providers
from .stages.character_sheet import build_character_sheet
from .stages.compose import compose
from .stages.cut_images import generate_cut_images
from .stages.narration import synthesize_narrations
from .stages.reference_sheets import build_reference_sheets
from .stages.review import build_review
from .stages.storyboard import plan_storyboard
from .stages.video_render import render_cut_videos

log = logging.getLogger(__name__)


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
        return await plan_storyboard(
            diary,
            llm=self.p.llm,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
        )

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
    ) -> dict[int, Path]:
        estimate = self.estimate(sb, only=only)
        log.info("예상 비용 $%.2f (상한 $%.2f)", estimate.total_usd, self.settings.max_cost_usd)
        enforce_budget(estimate, self.settings.max_cost_usd, confirm=confirm)
        return await render_cut_videos(
            sb,
            video=self.p.video,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
            only=only,
            force=force,
        )

    async def narrate(
        self, sb: Storyboard, *, only: set[int] | None = None, force: bool = False
    ) -> dict[int, Path]:
        return await synthesize_narrations(
            sb,
            tts=self.p.tts,
            prompts=self.prompts,
            settings=self.settings,
            job=self.job,
            only=only,
            force=force,
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
    ) -> Path:
        """승인된 컷 → 영상 → 나레이션 → final.mp4. 비싼 구간."""
        await self.render(sb, force=force, confirm=confirm)
        await self.narrate(sb, force=force)
        return self.compose(sb)

    def compose(self, sb: Storyboard, narrations: dict[int, Path] | None = None) -> Path:
        if narrations is None:
            narrations = {
                c.index: self.job.cut_narration(c.index)
                for c in sb.cuts
                if self.job.cut_narration(c.index).exists()
            }
        return compose(sb, job=self.job, settings=self.settings, narrations=narrations)
