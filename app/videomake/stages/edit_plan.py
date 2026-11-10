"""6'. 편집감독 — 정적을 자를 때 끝까지 보여줄 컷, 배경음악 구간을 정하고 음악을 만든다.

compose는 목소리가 끝난 뒤 남는 정적을 잘라 컷을 줄인다(settings.tight_edit). 무음 컷은 원래
자르지 않고, 여기서 고른 hold_cuts(문을 나서는 장면처럼 동작이 끝나야 의미가 사는 컷)도 남긴다.
배경음악은 처음부터 끝까지 빈틈없이 깐다(cover_all, 2026-11 릴스식). 목소리 아래에서는 compose가 줄인다.

LLM 호출 한 번(스토리보드 LLM과 같은 provider). 실패하면 기본 곡 하나로 전체를 덮고, 무음 컷만 남기고 자른다. 결과는 job/edit_plan.json에 남는다.
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


DEFAULT_MUSIC_PROMPT = (
    "Understated drama underscore, soft felt piano with warm strings, gentle and steady, medium-slow tempo, no vocals."
)


def cover_all(plan: EditPlan, sb: Storyboard) -> EditPlan:
    """음악 구간을 첫 컷부터 마지막 컷까지 빈틈없이 잇는다. 곡이 없으면 기본 곡 하나로 덮는다.
    plan은 checked()를 거쳐 구간이 정렬돼 있고 겹치지 않는다."""
    if not sb.cuts:
        return plan
    first, last = sb.cuts[0].index, sb.cuts[-1].index
    cues = list(plan.music) or [MusicCue(from_cut=first, to_cut=last, prompt=DEFAULT_MUSIC_PROMPT)]
    out: list[MusicCue] = []
    for k, cue in enumerate(cues):
        begin = first if not out else out[-1].to_cut + 1
        end = last if k == len(cues) - 1 else cue.to_cut
        if begin > end:  # 앞 곡이 이 구간을 이미 덮었다
            continue
        out.append(cue.model_copy(update={"from_cut": begin, "to_cut": end}))
    if out[-1].to_cut != last:
        out[-1] = out[-1].model_copy(update={"to_cut": last})
    return plan.model_copy(update={"music": out})


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
        return cover_all(cached.checked(sb), sb) if settings.music else cached.checked(sb)
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
    plan = plan.checked(sb)
    plan = cover_all(plan, sb) if settings.music else plan.model_copy(update={"music": []})
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
