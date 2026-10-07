"""장소 일관성 — 장소 시트(네 방향)와 조연 캐릭터 시트를 컷 그림의 레퍼런스로 넘긴다. 비용 0."""

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

CLASSROOM = "A training classroom. Entrance side: a wooden door. Far side: a whiteboard. Left side: tall windows. Right side: a beige wall with a clock."
PARKING = "An open outdoor parking lot beside a five-storey beige building."
FRIEND = {"name": "지수", "appearance": "A woman in her late twenties with shoulder-length brown hair, wearing a grey knit sweater.", "voice": "bright, mid-pitched"}


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)


class _RecordingImage(fake.FakeImage):
    def __init__(self):
        self.calls = []

    async def generate(self, *, prompt, dest, references=(), **kwargs):
        self.calls.append((_name(dest), prompt, [_name(r) for r in references], kwargs.get("aspect_ratio")))
        return await super().generate(prompt=prompt, dest=dest, references=references, **kwargs)


def _name(path):
    if path.name == "character_sheet.png":
        return "sheet:주인공"
    if path.parent.name == "sheets":
        return f"sheet:{path.stem}"
    return f"cut{path.parent.name}"


def _payload(cuts):
    """cuts: (장소, [(이름, 위치)]) 목록."""
    payload = fake.demo_storyboard_payload(len(cuts))
    payload["supporting"] = [FRIEND, {**FRIEND, "name": "엄마", "appearance": "A woman in her fifties."}]
    payload["locations"] = [
        {"name": "강의실", "description": CLASSROOM},
        {"name": "주차장", "description": PARKING},
        {"name": "안 쓰는 곳", "description": "Unused."},
    ]
    for cut, (loc, cast) in zip(payload["cuts"], cuts):
        cut["location"] = loc
        cut["cast"] = [{"name": n, "position": p} for n, p in cast]
    return payload


def _images(tmp_path, cuts):
    settings = Settings(_env_file=None, jobs_dir=tmp_path / "jobs", min_cuts=1, min_total_seconds=4)
    base = build_fake_providers(settings)
    llm = fake.FakeLLM(len(cuts))
    llm.payload = _payload(cuts)
    image = _RecordingImage()
    providers = base.__class__(**{**base.__dict__, "llm": llm, "image": image})
    pipe = Pipeline(providers=providers, job=JobStore(settings.jobs_dir, "loc"), settings=settings)
    asyncio.run(pipe.run_to_gate(DiaryInput(text="일기")))
    return {name: (prompt, refs, aspect) for name, prompt, refs, aspect in image.calls}


def test_sheets_are_made_for_used_places_and_on_screen_people_only(tmp_path):
    calls = _images(tmp_path, [
        ("주차장", [("지훈", "center")]),
        ("강의실", [("지훈", "left"), ("지수", "right")]),
        ("강의실", [("지훈", "center")]),
    ])

    sheets = sorted(n for n in calls if n.startswith("sheet:"))
    # 엄마는 화면에 나오지 않고 "안 쓰는 곳"은 어느 컷도 쓰지 않아 시트가 없다.
    assert sheets == ["sheet:character_01", "sheet:location_01", "sheet:location_02", "sheet:주인공"]
    assert calls["sheet:location_01"][2] == "1:1"
    assert "Four views of the same empty place" in calls["sheet:location_01"][0]


def test_cut_gets_its_cast_sheets_in_screen_order_and_its_place_sheet(tmp_path):
    calls = _images(tmp_path, [
        ("강의실", [("지수", "right"), ("지훈", "left")]),
        ("주차장", [("지훈", "center")]),
    ])

    assert calls["cut01"][1] == ["sheet:주인공", "sheet:character_01", "sheet:location_01"]
    assert calls["cut02"][1] == ["sheet:주인공", "sheet:location_02"]
    # 같은 장소 컷의 그림을 레퍼런스로 넘기지 않는다(시점까지 베꼈다).
    assert not any(r.startswith("cut") for _, refs, _ in calls.values() for r in refs)


def test_cut_prompt_places_people_and_forbids_copying_the_place_viewpoint(tmp_path):
    calls = _images(tmp_path, [("강의실", [("지훈", "left"), ("지수", "right")])])
    prompt = calls["cut01"][0]

    assert "1. Character reference sheet for 지훈." in prompt
    assert "2. Character reference sheet for 지수." in prompt
    assert "3. Location reference sheet" in prompt
    assert "지훈 is on the left side of the frame." in prompt
    assert "지수 is on the right side of the frame." in prompt
    assert CLASSROOM in prompt
    assert "Do NOT copy the viewpoint or composition" in prompt
    assert "강의실" not in prompt  # 장소 이름(한글)은 그림 모델에 넣지 않는다


def test_undefined_location_or_cast_is_rejected():
    with pytest.raises(ValidationError, match="장소 '도서관'가 장소 목록에 없다"):
        _StoryboardDraft.model_validate(_payload([("도서관", [("지훈", "center")])])).to_storyboard()
    with pytest.raises(ValidationError, match="인물 목록에 없다"):
        _StoryboardDraft.model_validate(_payload([("강의실", [("민수", "center")])])).to_storyboard()


def test_korean_location_description_is_fed_back():
    payload = _payload([("강의실", [("지훈", "center")])])
    payload["locations"][0]["description"] = "회색 바닥의 강의실"
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()

    fields = [v.field for v in lint_storyboard(sb) if v.rule == "영어로 작성"]
    assert fields == ["강의실.description"]
