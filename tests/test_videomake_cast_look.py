"""배우 캐스팅·드라마 화면·장소 확인·어깨너머 허용. 외부 API 없음, 비용 0."""

from app.videomake.config import Settings
from app.videomake.guardrails import lint_image_prompt
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.base import SeenFrame, SeenPerson
from app.videomake.stages.cut_images import image_problems, planned_side
from app.videomake.stages.storyboard import _StoryboardDraft, system_prompt


def _sb():
    payload = fake.demo_storyboard_payload(2)
    payload["cuts"][0]["image_prompt"] = "Camera faces the left side (the green counter), from near the door. " + payload["cuts"][0]["image_prompt"]
    return _StoryboardDraft.model_validate(payload).to_storyboard()


def _seen(**kw):
    return SeenFrame(people=[SeenPerson(gender="m", height_ratio=0.5)], looks_at_camera=False, **kw)


def test_planned_side_is_read_from_image_prompt():
    sb = _sb()
    assert planned_side(sb.cuts[0]) == "left"
    assert planned_side(sb.cuts[1]) == ""


def test_wrong_place_or_wrong_wall_is_redrawn():
    sb = _sb()
    cut = sb.cuts[0]
    assert image_problems(sb, cut, _seen(same_place=True, facing="left")) == []
    assert image_problems(sb, cut, _seen()) == []  # 장소 확인을 안 했으면 문제 없음
    assert any("same place" in p for p in image_problems(sb, cut, _seen(same_place=False, facing="left")))
    assert any("face the left side" in p for p in image_problems(sb, cut, _seen(same_place=True, facing="entrance")))


def test_characters_are_cast_as_original_attractive_actors():
    p = get_prompts()
    sheet = p.render("character_sheet.j2", name="민지", appearance="a woman", style_block=p.style_block)
    assert "current hit Netflix K-drama" in sheet and "idol-level visuals" in sheet
    assert "not a lookalike of a specific real person" in sheet
    system = system_prompt(p, Settings(_env_file=None))
    assert "한국 드라마 배우처럼 매력적으로" in system
    assert "실존 연예인 이름을 쓰거나 닮게 하지 않는다" in system


def test_frames_look_like_a_drama_not_a_snapshot():
    style = get_prompts().style_block
    assert "Korean TV drama" in style and "prime lens" in style
    assert "bystander" not in style


def test_places_have_landmarks_seen_from_every_side():
    p = get_prompts()
    assert "Everywhere:" in system_prompt(p, Settings(_env_file=None))
    sb = _sb()
    text = p.render("cut_image.j2", people=[], cast=[], image_prompt="x", location=sb.locations[0],
                    has_location_sheet=True, has_moment_image=False, camera_distance="full",
                    aspect_ratio="9:16", mood_block="", style_block="", thumbnail=False, solo_side="")
    assert "SAME PLACE IN EVERY SHOT" in text


def test_only_face_close_ups_are_banned_now():
    assert lint_image_prompt("An over-the-shoulder shot past his colleague toward Minji.") == []
    assert lint_image_prompt("An extreme close-up of her face.")
