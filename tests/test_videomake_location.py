"""장소 일관성 — 같은 장소의 컷은 같은 장소 설명과 첫 컷 그림을 기준으로 그린다. 비용 0."""

import asyncio
import shutil

import pytest
from pydantic import ValidationError

from app.videomake.config import Settings
from app.videomake.guardrails import lint_storyboard
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.registry import build_fake_providers
from app.videomake.stages.storyboard import _StoryboardDraft

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")

CLASSROOM = "A training classroom with grey tile floor, rows of two-person light-wood desks, large windows on the left wall and a whiteboard at the front."
PARKING = "An open outdoor parking lot beside a five-storey beige building."


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)


class _RecordingImage(fake.FakeImage):
    def __init__(self):
        self.calls = []

    async def generate(self, *, prompt, dest, references=(), **kwargs):
        # 컷 그림은 cuts/NN/image.png에 저장된다 — 그 NN으로 어느 컷인지, 무엇을 참고했는지 남긴다.
        def name(path):
            return "sheet" if path.name == "character_sheet.png" else f"cut{path.parent.name}"
        self.calls.append((name(dest), prompt, [name(r) for r in references]))
        return await super().generate(prompt=prompt, dest=dest, references=references, **kwargs)


def _payload(locations):
    payload = fake.demo_storyboard_payload(len(locations))
    payload["locations"] = [
        {"name": "강의실", "description": CLASSROOM},
        {"name": "주차장", "description": PARKING},
    ]
    for cut, loc in zip(payload["cuts"], locations):
        cut["location"] = loc
    return payload


def _images(tmp_path, locations):
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs", min_cuts=1, min_total_seconds=4)
    base = build_fake_providers(settings)
    llm = fake.FakeLLM(len(locations))
    llm.payload = _payload(locations)
    image = _RecordingImage()
    providers = base.__class__(**{**base.__dict__, "llm": llm, "image": image})
    pipe = Pipeline(providers=providers, job=JobStore(settings.jobs_dir, "loc"), settings=settings)
    asyncio.run(pipe.run_to_gate(DiaryInput(text="일기")))
    # 첫 호출은 캐릭터 시트다.
    return image.calls[1:]


def test_same_place_cuts_get_the_first_cut_as_reference(tmp_path):
    calls = _images(tmp_path, ["주차장", "강의실", "강의실", "강의실", "주차장"])

    # 장소마다 첫 컷(주차장 1번, 강의실 2번)을 먼저 그린 뒤 나머지를 그린다.
    assert [cut for cut, _, _ in calls[:2]] == ["cut01", "cut02"]
    refs = {cut: r for cut, _, r in calls}
    assert refs["cut01"] == ["sheet"]
    assert refs["cut02"] == ["sheet"]
    assert refs["cut03"] == ["sheet", "cut02"]
    assert refs["cut04"] == ["sheet", "cut02"]
    assert refs["cut05"] == ["sheet", "cut01"]


def test_place_description_and_same_room_rule_are_in_the_prompt(tmp_path):
    calls = _images(tmp_path, ["강의실", "강의실"])

    anchor_prompt, follow_prompt = calls[0][1], calls[1][1]
    assert CLASSROOM in anchor_prompt and CLASSROOM in follow_prompt
    assert "same room" not in anchor_prompt
    assert "It is the same room" in follow_prompt
    assert follow_prompt.startswith("Generate") and "The first attached image is the character" in follow_prompt
    # 장소 이름(한글)은 그림 모델에 넣지 않는다.
    assert "강의실" not in follow_prompt


def test_undefined_location_is_rejected():
    payload = _payload(["강의실", "도서관"])
    with pytest.raises(ValidationError, match="장소 '도서관'가 장소 목록에 없다"):
        _StoryboardDraft.model_validate(payload).to_storyboard()


def test_korean_location_description_is_fed_back():
    payload = _payload(["강의실"])
    payload["locations"][0]["description"] = "회색 바닥의 강의실"
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    fields = [v.field for v in lint_storyboard(sb) if v.rule == "영어로 작성"]
    assert fields == ["강의실.description"]
