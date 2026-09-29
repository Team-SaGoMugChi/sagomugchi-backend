"""prompts/ 로더. 프롬프트 문자열은 코드에 하드코딩하지 않는다."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import PROMPTS_DIR


class PromptLibrary:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or PROMPTS_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self.root)),
            undefined=StrictUndefined,  # 변수 누락을 조용히 넘기지 않는다
            keep_trailing_newline=True,
        )

    def raw(self, template: str, /) -> str:
        return (self.root / template).read_text(encoding="utf-8").strip()

    # template을 위치 전용으로 둔다. 템플릿 변수에 `name`이 있어서
    # 키워드 인자와 충돌하기 때문이다.
    def render(self, template: str, /, **ctx: object) -> str:
        return self._env.get_template(template).render(**ctx).strip()

    # 자주 쓰는 상수들
    @property
    def style_block(self) -> str:
        return self.raw("style_block.md")

    @property
    def distancing_rules(self) -> str:
        return self.raw("distancing_rules.md")

    @property
    def video_negative_prompt(self) -> str:
        return " ".join(self.raw("video_negative_prompt.txt").split())

    @property
    def video_negative_prompt_dialogue(self) -> str:
        """대사 컷용. 발화 금지어를 빼야 Veo가 입을 움직이고 목소리를 낸다."""
        return " ".join(self.raw("video_negative_prompt_dialogue.txt").split())


@lru_cache(maxsize=1)
def get_prompts() -> PromptLibrary:
    return PromptLibrary()
