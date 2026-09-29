"""1. StoryboardPlanner — 일기 + 감정분석 → N컷 스토리보드.

LLM 출력을 그대로 믿지 않는다. 가드레일 린터를 통과할 때까지 위반 내역을
피드백으로 넣어 재요청한다. LLM 호출은 컷당 1센트 미만이고 영상은 컷당 $0.80이므로,
여기서 반복하는 비용은 사실상 0이다.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from ..config import (
    DIALOGUE_MAX_CHARS,
    DIALOGUE_MAX_LINES,
    DIALOGUE_MIN_LINES,
    NARRATION_MAX_CHARS,
    Settings,
)
from ..errors import GuardrailViolation
from ..guardrails import lint_storyboard
from ..job import JobStore
from ..models import (
    CharacterProfile,
    Cut,
    DiaryInput,
    Distortion,
    Line,
    Stage,
    Storyboard,
)
from ..prompts import PromptLibrary
from ..providers.base import LLMProvider

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def _feedback(violations: list[str]) -> str:
    return (
        "\n\n## 직전 결과의 연출 원칙 위반\n\n"
        + "\n".join(f"- {v}" for v in violations)
        + "\n\n위 항목을 모두 고쳐서 다시 작성해라."
    )


class _LineDraft(BaseModel):
    speaker: str
    text: str


class _CutDraft(BaseModel):
    """LLM 출력용 스키마. 길이 위반을 예외가 아니라 린터 피드백으로 다루기 위해
    Cut의 엄격한 validator를 뺀 사본이다."""

    index: int
    image_prompt: str
    motion_prompt: str
    # 컷마다 둘 중 하나만 채운다. 빈 문자열/빈 배열이 "안 씀"을 뜻한다.
    # Optional 타입을 쓰면 구조화 출력 스키마가 nullable이 되어 LLM이 헷갈린다.
    narration: str
    dialogue: list[_LineDraft]
    camera_distance: Literal["wide", "full", "medium"]


class _StoryboardDraft(BaseModel):
    protagonist: CharacterProfile
    supporting: list[CharacterProfile] = Field(default_factory=list)
    distortions: list[Distortion] = Field(default_factory=list)
    cuts: list[_CutDraft]

    def to_storyboard(self, duration_seconds: int) -> Storyboard:
        return Storyboard(
            protagonist=self.protagonist,
            supporting=self.supporting,
            distortions=self.distortions,
            cuts=[
                Cut(
                    index=c.index,
                    image_prompt=c.image_prompt,
                    motion_prompt=c.motion_prompt,
                    narration=c.narration.strip() or None,
                    dialogue=[Line(**line.model_dump()) for line in c.dialogue],
                    camera_distance=c.camera_distance,
                    duration_seconds=duration_seconds,
                )
                for c in self.cuts
            ],
        )


async def plan_storyboard(
    diary: DiaryInput,
    *,
    llm: LLMProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore | None = None,
) -> Storyboard:
    system = prompts.render(
        "storyboard_planner.system.md",
        n_cuts=settings.n_cuts,
        distancing_rules=prompts.distancing_rules,
        protagonist_hint=diary.protagonist_name or "주인공",
        narration_max_chars=NARRATION_MAX_CHARS,
        dialogue_max_chars=DIALOGUE_MAX_CHARS,
        dialogue_max_lines=DIALOGUE_MAX_LINES,
        dialogue_min_lines=DIALOGUE_MIN_LINES,
    )
    user = prompts.render(
        "storyboard_planner.user.j2",
        diary_text=diary.text,
        emotion_json=json.dumps(diary.emotion, ensure_ascii=False, indent=2),
        protagonist_name=diary.protagonist_name,
        n_cuts=settings.n_cuts,
    )

    started = time.perf_counter()
    feedback = ""
    last_violations: list[str] = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft, meta = await llm.complete_json(
            system=system, user=user + feedback, schema=_StoryboardDraft
        )
        log.info(
            "스토리보드 시도 %d/%d — %.1fs, in=%d out=%d tokens",
            attempt, MAX_ATTEMPTS, meta.elapsed_s, meta.input_tokens, meta.output_tokens,
        )
        if job is not None:
            job.record_cost(f"storyboard attempt {attempt}", meta.cost_usd)

        if len(draft.cuts) != settings.n_cuts:
            last_violations = [f"컷이 {len(draft.cuts)}개다. 정확히 {settings.n_cuts}개여야 한다."]
        else:
            try:
                sb = draft.to_storyboard(settings.cut_duration_seconds)
            except ValidationError as exc:
                # 나레이션/대사 배타 규칙이나 길이 상한 위반. 예외로 죽이지 않고
                # 다른 위반과 똑같이 피드백으로 돌려준다.
                last_violations = [
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors()
                ]
                log.warning("가드레일 위반 %d건, 재요청", len(last_violations))
                feedback = _feedback(last_violations)
                continue
            violations = lint_storyboard(sb)
            if not violations:
                if job is not None:
                    job.save_storyboard(sb)
                    job.record_stage(
                        Stage.STORYBOARD,
                        elapsed_s=time.perf_counter() - started,
                        attempts=attempt,
                    )
                return sb
            last_violations = [str(v) for v in violations]

        log.warning("가드레일 위반 %d건, 재요청", len(last_violations))
        feedback = _feedback(last_violations)

    raise GuardrailViolation(
        f"{MAX_ATTEMPTS}회 시도했으나 연출 원칙을 만족하는 스토리보드를 얻지 못했다:\n"
        + "\n".join(f"  - {v}" for v in last_violations)
    )
