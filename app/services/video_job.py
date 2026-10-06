"""일기 Step3 영상 생성 작업 관리.

videomake 파이프라인은 수 분이 걸리므로 요청 한 번으로 기다리지 않는다.
작업을 등록하고(start) 백그라운드에서 돌린 뒤, 앱은 상태를 폴링(status)한다.

- 승인 게이트: 앱 사용자는 컷 이미지를 검수할 수 없으므로 이미지 단계가 끝나면
  서버가 전 컷을 자동 승인한다. 비용 상한(VIDEOMAKE_MAX_COST_USD)은 그대로 적용돼
  넘으면 렌더하지 않고 failed가 된다.
- 진행률: 단계별 산출물 파일 개수로 계산한다. JobStore가 이미 파일로 상태를
  남기므로 별도 기록이 필요 없다.
- 작업 상태는 메모리에만 둔다. 서버를 재시작하면 진행 중이던 작업은 사라진다
  (생성물 파일은 jobs_dir에 남는다). 여러 인스턴스로 배포할 때 DB로 옮길 것.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.models.video import VideoJobRequest, VideoJobStatus, VideoStage
from app.videomake.config import Settings, get_settings
from app.videomake.errors import BudgetExceeded, GuardrailViolation, VideomakeError
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.providers.registry import build_providers

log = logging.getLogger(__name__)

_FAILED_DEFAULT = "영상을 만들지 못했어요. 잠시 후 다시 시도해주세요."


def to_diary_input(req: VideoJobRequest) -> DiaryInput:
    """Step2 분석 결과 → videomake 입력.

    스토리보드 LLM은 emotion을 JSON 그대로 읽으므로 키 이름을 videomake 예시
    (examples/diary.sample.json)와 맞추고, 값이 없는 키는 넣지 않는다.
    """
    emotion: dict = {}
    if req.emotion_keywords:
        emotion["primary"] = req.emotion_keywords[0]
        if len(req.emotion_keywords) > 1:
            emotion["secondary"] = req.emotion_keywords[1:]
    if req.emotion_intensity is not None:
        emotion["intensity"] = round(req.emotion_intensity / 100, 2)
    if req.emotion_scores:
        emotion["scores"] = req.emotion_scores
    return DiaryInput(text=req.text, emotion=emotion, protagonist_name=req.protagonist_name)


@dataclass
class _JobState:
    status: str = "running"
    error: str | None = None


class VideoJobManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._jobs: dict[str, _JobState] = {}

    def create(self) -> str:
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = _JobState()
        return job_id

    async def run(self, job_id: str, req: VideoJobRequest) -> None:
        """백그라운드 태스크 본체. 예외를 밖으로 던지지 않고 상태에 남긴다."""
        state = self._jobs[job_id]
        if not self.settings.dummy:
            log.warning(
                "영상 작업 %s: 실제 생성 모드(VIDEOMAKE_DUMMY=false) — 과금된다 (상한 $%s)",
                job_id,
                self.settings.max_cost_usd,
            )
        try:
            pipe = Pipeline(
                providers=build_providers(self.settings),
                job=self._store(job_id),
                settings=self.settings,
            )
            sb = await pipe.run_to_gate(to_diary_input(req))
            pipe.approve(sb)
            await pipe.finish(sb)
            state.status = "done"
        except BudgetExceeded as exc:
            log.warning("영상 작업 %s 비용 상한 초과: %s", job_id, exc)
            state.status, state.error = "failed", "영상 생성 비용 상한을 넘어 중단했어요."
        except GuardrailViolation as exc:
            log.warning("영상 작업 %s 스토리보드 실패: %s", job_id, exc)
            state.status, state.error = "failed", "이 일기로는 영상을 구성하지 못했어요."
        except VideomakeError:
            log.exception("영상 작업 %s 실패", job_id)
            state.status, state.error = "failed", _FAILED_DEFAULT
        except Exception:
            log.exception("영상 작업 %s 예기치 못한 오류", job_id)
            state.status, state.error = "failed", _FAILED_DEFAULT

    def status(self, job_id: str) -> VideoJobStatus | None:
        state = self._jobs.get(job_id)
        if state is None:
            return None
        stage, progress = self._progress(job_id)
        if state.status == "done":
            stage, progress = "done", 1.0
        return VideoJobStatus(
            job_id=job_id,
            status=state.status,
            stage=stage,
            progress=progress,
            error=state.error,
            video_url=f"/video/jobs/{job_id}/file" if state.status == "done" else None,
        )

    def final_path(self, job_id: str) -> Path | None:
        state = self._jobs.get(job_id)
        if state is None or state.status != "done":
            return None
        path = self._store(job_id).final_path
        return path if path.exists() else None

    def _store(self, job_id: str) -> JobStore:
        return JobStore(self.settings.jobs_dir, job_id)

    def _progress(self, job_id: str) -> tuple[VideoStage, float]:
        """산출물 개수로 단계·진행률을 계산한다.

        비중은 실제 소요 시간 기준이다. Veo 렌더가 대부분을 차지한다.
        """
        job = self._store(job_id)
        if not job.storyboard_path.exists():
            return "storyboard", 0.0
        # 컷 수는 일기마다 스토리보드가 정한다.
        storyboard = job.load_storyboard()
        n = len(storyboard.cuts)

        def count(path_of) -> int:
            return sum(1 for i in range(1, n + 1) if path_of(i).exists())

        images = count(job.cut_image) + int(job.character_sheet_path.exists())
        if images < n + 1:
            return "images", 0.05 + 0.25 * images / (n + 1)
        videos = count(job.cut_video)
        if videos < n:
            return "videos", 0.30 + 0.60 * videos / n
        # 대사 컷은 Veo가 직접 말하므로 나레이션 파일이 없다.
        narrated = [c.index for c in storyboard.cuts if not c.is_dialogue]
        done = sum(1 for i in narrated if job.cut_narration(i).exists())
        if done < len(narrated):
            return "narration", 0.90 + 0.05 * done / len(narrated)
        return "compose", 0.95


@lru_cache
def get_video_jobs() -> VideoJobManager:
    return VideoJobManager()
