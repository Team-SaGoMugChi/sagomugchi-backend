"""배우 캐스팅·드라마 화면·장소 확인·어깨너머 허용. 외부 API 없음, 비용 0."""

from app.videomake.config import Settings
from app.videomake.guardrails import lint_image_prompt
from app.videomake.prompts import get_prompts
from app.videomake.providers import fake
from app.videomake.providers.base import SeenFrame, SeenPerson
from app.videomake.stages.cut_images import cut_image_request, image_problems, planned_side
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


def test_extra_or_cloned_person_in_a_cut_image_is_redrawn():
    sb = _sb()
    cut = sb.cuts[0]  # 한 사람 컷
    two = SeenFrame(people=[SeenPerson(gender="m", height_ratio=0.5), SeenPerson(gender="m", height_ratio=0.4)],
                    looks_at_camera=False)
    assert any("Remove the extra person" in p for p in image_problems(sb, cut, two))
    clone = _seen(duplicate_person=True)
    assert any("appears twice" in p for p in image_problems(sb, cut, clone))


def test_split_frame_is_redrawn_and_prompt_forbids_panels():
    sb = _sb()
    cut = sb.cuts[0]
    assert any("ONE continuous view" in p for p in image_problems(sb, cut, _seen(split_frame=True)))
    assert not any("panels" in p for p in image_problems(sb, cut, _seen()))
    p = get_prompts()
    text = p.render("cut_image.j2", people=[], cast=[], image_prompt="x", location=sb.locations[0],
                    has_location_sheet=True, has_moment_image=False, camera_distance="full",
                    aspect_ratio="9:16", mood_block="", style_block="", thumbnail=False, solo_side="")
    assert "do NOT copy its grid layout" in text and "never panels" in text


def test_only_framing_or_wall_problems_do_not_redraw():
    from app.videomake.stages.cut_images import MEDIUM_PROBLEM, needs_redraw

    sb = _sb()
    cut = sb.cuts[0]
    wall = "The camera must face the left side of the place as written in SCENE, not the far side."
    assert not needs_redraw(cut, [wall])
    assert not needs_redraw(cut.model_copy(update={"dialogue": []}), [MEDIUM_PROBLEM, wall])
    assert needs_redraw(cut, [wall, "Someone looks into the camera. Nobody may look at the camera."])
    from app.videomake.models import Line

    talking = cut.model_copy(update={"narration": None, "dialogue": [Line(speaker=cut.cast[0].name, text="고마워.")]})
    assert needs_redraw(talking, [MEDIUM_PROBLEM])  # 대사 컷은 입 모양이 보여야 한다


def test_crowd_place_keeps_background_people_and_rooms_share_a_reference():
    from app.videomake.stages.cut_images import room_shot
    from app.videomake.stages.video_render import _without_crowd_terms

    sb = _sb()
    cut = sb.cuts[0]
    extra = _seen(same_place=True)
    extra = extra.model_copy(update={"people": extra.people * 6, "unknown_person": True})
    assert any("Remove the extra person" in p for p in image_problems(sb, cut, extra))

    locs = [loc.model_copy(update={"background_people": "relatives at the other tables"}) if loc.name == cut.location
            else loc for loc in sb.locations]
    party = sb.model_copy(update={"locations": locs})
    problems = image_problems(party, cut, extra)
    assert not any("extra person" in p or "not in the cast" in p for p in problems)

    prompt, _ = cut_image_request(party, cut, sheets={}, location_sheets={}, prompts=get_prompts(), aspect_ratio="9:16")
    assert "BACKGROUND PEOPLE" in prompt and "relatives at the other tables" in prompt

    same = [c for c in sb.cuts if c.location == cut.location]
    assert len(same) > 1
    far = "Camera faces the far side (the stage), from the entrance. "
    left = "Camera faces the left side (the windows), from the right. "
    a, b = same[0], same[1]
    room = sb.model_copy(update={"cuts": [
        c.model_copy(update={"image_prompt": far + c.image_prompt}) if c is a
        else c.model_copy(update={"image_prompt": far + c.image_prompt}) if c is b else c for c in sb.cuts]})
    assert room_shot(room, room.cuts[sb.cuts.index(a)]) is None
    assert room_shot(room, room.cuts[sb.cuts.index(b)]) == a.index
    # 다른 벽을 보는 컷에는 참고 그림을 주지 않는다 — 그 각도를 따라 그렸다.
    turned = room.model_copy(update={"cuts": [
        c.model_copy(update={"image_prompt": left + b.image_prompt}) if c.index == b.index else c for c in room.cuts]})
    assert room_shot(turned, turned.cuts[sb.cuts.index(b)]) is None

    # 허리 위 샷은 등장인물만 본다 — 다리가 안 보이는 뒤쪽 손님이 있어도 전신이면 다시 그린다.
    medium = cut.model_copy(update={"camera_distance": "medium"})
    full_body = _seen(same_place=True)
    lead = full_body.people[0].model_copy(update={"height_ratio": 0.75, "legs_visible": True})
    guest = lead.model_copy(update={"height_ratio": 0.15, "legs_visible": False})
    full_body = full_body.model_copy(update={"people": [lead] * len(party.visible_cast(medium)) + [guest] * 5})
    assert any(p.startswith("This must be a MEDIUM") for p in image_problems(party, medium, full_body))
    # 손님이 있는 곳이라도 화면 끝에 잘린 낯선 사람은 다시 그린다.
    edge = _seen(same_place=True, cut_off_person=True)
    assert any("cut off at the edge" in p for p in image_problems(party, cut, edge))
    assert _without_crowd_terms("crowd, extra people, flickering, bystanders") == "flickering"


def test_dialogue_needs_the_pair_shown_together_first():
    from app.videomake.guardrails import lint_dialogue_staging
    from app.videomake.models import CastMember, Line

    sb = _sb()
    friend = sb.protagonist.model_copy(update={"name": "수아"})
    sb = sb.model_copy(update={"supporting": [*sb.supporting, friend]})
    a, b = sb.cuts[0], sb.cuts[1]
    me, other = sb.protagonist.name, "수아"
    talk = a.model_copy(update={"narration": None, "dialogue": [Line(speaker=me, text="고마워.")],
                                "cast": [CastMember(name=me, position="left")]})
    pair = b.model_copy(update={"location": a.location,
                                "cast": [CastMember(name=me, position="left"), CastMember(name=other, position="right")]})
    late = sb.model_copy(update={"cuts": [talk, pair, *sb.cuts[2:]]})
    assert any("먼저" in v.rule for v in lint_dialogue_staging(late))
    early = sb.model_copy(update={"cuts": [pair.model_copy(update={"index": a.index}),
                                           talk.model_copy(update={"index": b.index}), *sb.cuts[2:]]})
    assert lint_dialogue_staging(early) == []
    moved = talk.model_copy(update={"index": b.index, "cast": [CastMember(name=me, position="center")]})
    wrong_side = sb.model_copy(update={"cuts": [pair.model_copy(update={"index": a.index}), moved, *sb.cuts[2:]]})
    assert any("같은 자리" in v.rule for v in lint_dialogue_staging(wrong_side))


def test_seated_person_must_stay_at_their_seat():
    from app.videomake.stages.cut_images import seat_lines

    sb = _sb()
    cut = sb.cuts[0]
    name = sb.visible_cast(cut)[0].name
    seated = cut.model_copy(update={"image_prompt": f"Camera faces the left side. {name} sits on the right at the "
                                                    "honor table in front of the folding screen, smiling."})
    sb = sb.model_copy(update={"cuts": [seated, *sb.cuts[1:]]})
    assert seat_lines(sb, seated) == [f"{name}: at the honor table in front of the folding screen"]
    moved = _seen(same_place=True, facing="left", wrong_seat=[name])
    assert any(p.startswith(f"{name} must be at the honor table") for p in image_problems(sb, seated, moved))
    assert image_problems(sb, seated, _seen(same_place=True, facing="left")) == []


def test_solo_speaker_shot_hides_the_empty_seat_and_keeps_the_time_of_day():
    """혼자 보이는 대사 컷: 빈 맞은편 자리가 보이면 다시 그리고, 앞 컷 그림은 참고로 주지 않는다.
    밤 장면이 대낮으로 그려지면 다시 그린다."""
    from app.videomake.models import CastMember, Line
    from app.videomake.stages.cut_images import planned_time, solo_listener_side

    sb = _sb()
    friend = sb.protagonist.model_copy(update={"name": "수아"})
    sb = sb.model_copy(update={"supporting": [*sb.supporting, friend]})
    a, b = sb.cuts[0], sb.cuts[1]
    me = sb.protagonist.name
    pair = a.model_copy(update={"cast": [CastMember(name=me, position="left"), CastMember(name="수아", position="right")],
                                "image_prompt": "Camera faces the left side. Both sit at the table, at night."})
    talk = b.model_copy(update={"location": a.location, "narration": None, "camera_distance": "medium",
                                "dialogue": [Line(speaker=me, text="미안해.")],
                                "cast": [CastMember(name=me, position="left")],
                                "image_prompt": "Camera faces the left side. 서연 sits at the table, evening."})
    sb = sb.model_copy(update={"cuts": [pair, talk, *sb.cuts[2:]]})
    assert solo_listener_side(sb, talk, sb.visible_cast(talk)) == "right"

    close = _seen(same_place=True, facing="left").model_copy(update={"people": [
        _seen().people[0].model_copy(update={"height_ratio": 0.7, "legs_visible": False})]})
    assert image_problems(sb, talk, close) == []
    empty = close.model_copy(update={"empty_seat": True})
    assert any("empty chair" in p for p in image_problems(sb, talk, empty))
    # 허리 위로는 부족하다 — 가슴 위로 가깝게(맞은편 자리가 안 보이게).
    waist = close.model_copy(update={"people": [close.people[0].model_copy(update={"height_ratio": 0.4})]})
    assert any(p.startswith("This must be a MEDIUM") for p in image_problems(sb, talk, waist))

    assert planned_time(talk) == "night"
    sunny = close.model_copy(update={"time_of_day": "day"})
    assert any(p.startswith("It is night") for p in image_problems(sb, talk, sunny))

    prompt, refs = cut_image_request(sb, talk, sheets={}, location_sheets={}, prompts=get_prompts(),
                                     aspect_ratio="9:16")
    assert "never show an empty chair" in prompt and "chest up" in prompt
    assert "NOT an over-the-shoulder shot" in prompt and "over-the-shoulder shot from behind" not in prompt
    back = close.model_copy(update={"foreground_back": True})
    assert any("not an over-the-shoulder" in p for p in image_problems(sb, talk, back))
    assert not any("over-the-shoulder" in p for p in image_problems(sb, sb.cuts[0], back))  # 두 사람 컷은 괜찮다
