"""6'. 편집감독 — 정적을 자를 때 끝까지 보여줄 컷, 배경음악 구간을 정하고 음악을 만든다.

compose는 목소리가 끝난 뒤 남는 정적을 잘라 컷을 줄인다(settings.tight_edit). 무음 컷은 원래
자르지 않고, 여기서 고른 hold_cuts(문을 나서는 장면처럼 동작이 끝나야 의미가 사는 컷)도 남긴다.
배경음악은 대부분 넣지 않고, 감정이 크게 움직이는 구간에만 작게 깐다(settings.music_level_db).

LLM 호출 한 번(스토리보드 LLM과 같은 provider). 실패하거나 더미 모드면 빈 계획 — 음악 없이,
무음 컷만 남기고 자른다. 결과는 job/edit_plan.json에 남는다.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from pydantic import BaseModel

from ..config import Settings
from ..job import JobStore
from ..models import EditPlan, MusicCue, Storyboard
from ..prompts import PromptLibrary
from ..providers.base import LLMProvider, MusicProvider

log = logging.getLogger(__name__)


class _MusicDraft(BaseModel):
    from_cut: int
    to_cut: int
    prompt: str


class _EditPlanDraft(BaseModel):
    """구조화 출력용 — 기본값 없이 모든 칸을 채우게 한다."""

    reason: str
    hold_cuts: list[int]
    music: list[_MusicDraft]


def cut_table(sb: Storyboard) -> str:
    rows = []
    for c in sb.cuts:
        if c.dialogue:
            voice = "대사: " + " / ".join(f"{line.speaker} \"{line.text}\"" for line in c.dialogue)
        elif c.narration:
            voice = f"나레이션: \"{c.narration}\""
        else:
            voice = "무음 컷(화면만)"
        rows.append(f"- 컷 {c.index} · {c.duration_seconds}초 · 감정 {c.mood} · {voice}\n  동작: {c.motion_prompt[:220]}")
    return "\n".join(rows)


def plan_path(job: JobStore) -> Path:
    return job.dir / "edit_plan.json"


def load_plan(job: JobStore) -> EditPlan | None:
    p = plan_path(job)
    if not p.exists():
        return None
    return EditPlan.model_validate_json(p.read_text(encoding="utf-8"))


async def plan_edit(
    sb: Storyboard,
    *,
    llm: LLMProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    force: bool = False,
) -> EditPlan:
    cached = None if force else load_plan(job)
    if cached is not None:
        return cached.checked(sb)
    plan = EditPlan()
    if not settings.dummy:
        try:
            draft, result = await llm.complete_json(
                system=prompts.render("edit_plan.system.md"),
                user="## 컷 목록\n\n" + cut_table(sb),
                schema=_EditPlanDraft,
            )
            job.record_cost("edit_plan_llm", result.cost_usd)
            plan = EditPlan(
                reason=draft.reason,
                hold_cuts=draft.hold_cuts,
                music=[MusicCue(**m.model_dump()) for m in draft.music if m.prompt.strip()],
            )
        except Exception:
            log.exception("편집 계획 실패 — 음악 없이, 무음 컷만 남기고 자른다")
    if not settings.music:
        plan = plan.model_copy(update={"music": []})
    plan = plan.checked(sb)
    plan_path(job).write_text(json.dumps(plan.model_dump(), ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("편집 계획: 남길 컷 %s, 음악 %d구간 — %s", plan.hold_cuts, len(plan.music), plan.reason)
    return plan


async def make_music(
    plan: EditPlan, *, music: MusicProvider | None, job: JobStore, force: bool = False
) -> dict[int, Path]:
    """음악 구간 번호(0부터) → 곡 파일. 한 곡이 실패하면 그 구간은 음악 없이 간다."""
    if music is None or not plan.music:
        return {}

    async def one(k: int, cue: MusicCue) -> tuple[int, Path | None]:
        dest = job.dir / "music" / f"cue{k}.wav"
        if dest.exists() and not force:
            return k, dest
        try:
            result = await music.generate(prompt=cue.prompt, dest=dest)
        except Exception:
            log.exception("배경음악 %d 생성 실패 — 그 구간은 음악 없이", k)
            return k, None
        job.record_cost(f"music{k}", result.cost_usd)
        return k, dest

    pairs = await asyncio.gather(*(one(k, cue) for k, cue in enumerate(plan.music)))
    return {k: p for k, p in pairs if p is not None}
