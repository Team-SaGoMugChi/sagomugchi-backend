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


def test_only_framing_problems_do_not_redraw():
    from app.videomake.stages.cut_images import MEDIUM_PROBLEM, needs_redraw

    sb = _sb()
    cut = sb.cuts[0]
    wall = "The camera must face the left side of the place as written in SCENE, not the far side."
    # 다른 벽을 그리면 같은 자리인데 배경이 달라져 다시 그린다(2026-11 카페).
    assert needs_redraw(cut, [wall])
    assert not needs_redraw(cut.model_copy(update={"dialogue": []}), [MEDIUM_PROBLEM])
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


def test_dialogue_shot_is_over_the_shoulder_and_keeps_the_time_of_day():
    """대사 컷은 어깨너머 샷: 상대 뒷모습이 앞쪽에 있어야 하고(없으면 상대가 사라져 보인다), 빈 자리는 안 된다.
    밤 장면이 대낮으로 그려지면 다시 그린다."""
    from app.videomake.models import CastMember, Line
    from app.videomake.stages.cut_images import check_people, ots_partner, planned_time, solo_listener_side

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
    assert ots_partner(sb, talk) == CastMember(name="수아", position="right")
    assert any("seen from behind" in p for p in check_people(sb, talk))

    speaker = _seen().people[0].model_copy(update={"height_ratio": 0.7, "legs_visible": False, "gender": ""})
    ots = _seen(same_place=True, facing="left").model_copy(update={"people": [speaker, speaker],
                                                                   "foreground_back": True})
    assert image_problems(sb, talk, ots) == []
    alone = ots.model_copy(update={"people": [speaker], "foreground_back": False})
    assert any("seen from behind" in p for p in image_problems(sb, talk, alone))  # 상대가 사라졌다
    empty = ots.model_copy(update={"empty_seat": True})
    assert any("empty chair" in p for p in image_problems(sb, talk, empty))

    assert planned_time(talk) == "night"
    sunny = ots.model_copy(update={"time_of_day": "day"})
    assert any(p.startswith("It is night") for p in image_problems(sb, talk, sunny))

    prompt, _ = cut_image_request(sb, talk, sheets={}, location_sheets={}, prompts=get_prompts(), aspect_ratio="9:16")
    assert "OVER-THE-SHOULDER SHOT" in prompt and "수아" in prompt and "There is no empty chair" in prompt


def test_dialogue_shots_keep_one_camera_side_per_seat():
    """같은 사람 대사 컷은 같은 방향, 마주한 상대는 반대 방향 — 어기면 시나리오를 다시 요청한다."""
    from app.videomake.guardrails import lint_dialogue_camera
    from app.videomake.models import CastMember, Line

    sb = _sb()
    friend = sb.protagonist.model_copy(update={"name": "수아"})
    sb = sb.model_copy(update={"supporting": [*sb.supporting, friend]})
    base = sb.cuts[0]
    me = sb.protagonist.name

    def talk(index, who, side, pos):
        return base.model_copy(update={
            "index": index, "narration": None, "dialogue": [Line(speaker=who, text="응.")],
            "cast": [CastMember(name=who, position=pos)],
            "image_prompt": f"Camera faces the {side} side, from the table. {who} sits at the table.",
        })

    pair = base.model_copy(update={"index": 1, "cast": [CastMember(name=me, position="left"),
                                                        CastMember(name="수아", position="right")]})
    good = [pair, talk(2, me, "right", "left"), talk(3, "수아", "left", "right"), talk(4, me, "right", "left")]
    assert lint_dialogue_camera(sb.model_copy(update={"cuts": good})) == []
    moved = [*good[:3], talk(4, me, "entrance", "left")]
    assert any("같은 카메라 방향" in v.rule for v in lint_dialogue_camera(sb.model_copy(update={"cuts": moved})))
    same = [pair, talk(2, me, "right", "left"), talk(3, "수아", "right", "right")]
    assert any("반대 방향" in v.rule for v in lint_dialogue_camera(sb.model_copy(update={"cuts": same})))


def test_floor_plan_goes_into_sheet_and_cut_prompts():
    sb = _sb()
    plan = "Down the middle: two rows of three square tables (six tables)."
    locs = [loc.model_copy(update={"floor_plan": plan}) for loc in sb.locations]
    sb = sb.model_copy(update={"locations": locs})
    cut = sb.cuts[0]
    sheet = get_prompts().render("location_sheet.j2", description=locs[0].description, floor_plan=plan,
                                 style_block="")
    assert plan in sheet and "Count the furniture" in sheet
    prompt, _ = cut_image_request(sb, cut, sheets={}, location_sheets={}, prompts=get_prompts(), aspect_ratio="9:16")
    assert plan in prompt


def test_side_panel_is_cut_from_the_sheet_and_plates_are_per_seat(tmp_path):
    """장소 시트에서 그 벽 칸만 잘라 참고로 준다. 대사 컷 배경판은 (장소, 말하는 사람, 방향)마다 한 장."""
    import shutil
    import subprocess

    import pytest

    from app.videomake.job import JobStore
    from app.videomake.models import CastMember, Line
    from app.videomake.stages.cut_images import plate_key, side_panel

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg 필요")
    sheet = tmp_path / "sheet.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=200x200", "-frames:v", "1",
                    str(sheet)], check=True)
    job = JobStore(tmp_path, "j")
    job.dir.mkdir(parents=True, exist_ok=True)
    panel = side_panel(job, sheet, "right")
    assert panel is not None and panel.exists()
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                          str(panel)], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "100,100"
    assert side_panel(job, sheet, "") is None

    sb = _sb()
    friend = sb.protagonist.model_copy(update={"name": "수아"})
    sb = sb.model_copy(update={"supporting": [*sb.supporting, friend]})
    me = sb.protagonist.name
    base = sb.cuts[0]
    pair = base.model_copy(update={"cast": [CastMember(name=me, position="left"), CastMember(name="수아", position="right")]})
    talk = sb.cuts[1].model_copy(update={
        "location": base.location, "narration": None, "dialogue": [Line(speaker=me, text="응.")],
        "cast": [CastMember(name=me, position="left")], "image_prompt": "Camera faces the right side. 서연 sits."})
    sb = sb.model_copy(update={"cuts": [pair, talk, *sb.cuts[2:]]})
    assert plate_key(sb, talk) == (base.location, me, "right")
    assert plate_key(sb, pair) is None  # 두 사람 컷은 배경판 대신 벽 칸을 쓴다


def test_window_side_catches_a_mirrored_room_and_same_seat_keeps_distance():
    """창이 왼쪽 벽이면 안쪽을 볼 땐 화면 왼쪽, 입구를 볼 땐 화면 오른쪽 — 반대면 다시 그린다."""
    from app.videomake.guardrails import lint_dialogue_camera
    from app.videomake.models import CastMember, Line
    from app.videomake.stages.cut_images import WINDOW_PROBLEM, frame_window_side

    desc = ("Everywhere: beige walls. Entrance side: a glass door. Far side: a counter. "
            "Left side: tall street-facing windows. Right side: a bookshelf wall.")
    assert frame_window_side(desc, "far") == "left"
    assert frame_window_side(desc, "entrance") == "right"
    assert frame_window_side(desc, "left") == ""  # 창이 정면 — 좌우를 따지지 않는다
    assert frame_window_side("Left side: windows. Right side: windows.", "far") == ""  # 양쪽이면 모른다

    sb = _sb()
    locs = [loc.model_copy(update={"description": desc}) for loc in sb.locations]
    cut = sb.cuts[0].model_copy(update={"image_prompt": "Camera faces the entrance side. 서연 stands."})
    sb = sb.model_copy(update={"locations": locs, "cuts": [cut, *sb.cuts[1:]]})
    mirrored = _seen(same_place=True, facing="entrance").model_copy(update={"window_side": "left"})
    assert WINDOW_PROBLEM.format(want="right") in image_problems(sb, cut, mirrored)
    right = mirrored.model_copy(update={"window_side": "right"})
    assert not any("wrong side" in p for p in image_problems(sb, cut, right))

    friend = sb.protagonist.model_copy(update={"name": "수아"})
    sb = sb.model_copy(update={"supporting": [*sb.supporting, friend]})
    me = sb.protagonist.name

    def talk(index, distance):
        return cut.model_copy(update={
            "index": index, "narration": None, "dialogue": [Line(speaker=me, text="응.")],
            "cast": [CastMember(name=me, position="left")], "camera_distance": distance,
            "image_prompt": "Camera faces the right side. 서연 sits."})

    pair = cut.model_copy(update={"cast": [CastMember(name=me, position="left"), CastMember(name="수아", position="right")]})
    cuts = [pair, talk(2, "medium"), talk(3, "full")]
    assert any("같은 거리" in v.rule for v in lint_dialogue_camera(sb.model_copy(update={"cuts": cuts})))


def test_light_of_later_cuts_is_matched_to_the_first_cut_of_the_place(tmp_path):
    import shutil
    import subprocess

    import pytest

    from app.videomake.job import JobStore
    from app.videomake.stages.cut_images import _mean_rgb, match_light

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg 필요")
    sb = _sb()
    same = [c for c in sb.cuts if c.location == sb.cuts[0].location]
    assert len(same) > 1
    job = JobStore(tmp_path, "j")
    for c, color in zip(same, ["0x504030", "0x705030"]):
        job.cut_dir(c.index).mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=64x64",
                        "-frames:v", "1", str(job.cut_image(c.index))], check=True)
    match_light(sb, job, {c.index for c in same})
    r, g, b = _mean_rgb(job.cut_image(same[1].index))
    assert r < 0x70 * 0.9  # 붉게 뜬 컷이 첫 컷 쪽으로 당겨졌다
    assert (job.cut_dir(same[1].index) / "image_before_light.png").exists()


def _room(path, seed):
    import cv2
    import numpy as np

    rng = np.random.default_rng(seed)
    im = np.full((1280, 720, 3), 200, np.uint8)
    for _ in range(400):
        x, y = int(rng.integers(0, 720)), int(rng.integers(0, 1280))
        color = tuple(int(c) for c in rng.integers(0, 255, 3))
        cv2.rectangle(im, (x, y), (x + int(rng.integers(8, 60)), y + int(rng.integers(8, 60))), color, -1)
    cv2.imwrite(str(path), im)
    return im


def test_plate_match_tells_the_same_wall_from_another_wall(tmp_path):
    import cv2

    from app.videomake.stages.cut_images import PLATE_MIN_MATCH, plate_match

    plate = tmp_path / "plate.png"
    room = _room(plate, 1)
    # 같은 벽을 조금 당겨 찍고 사람(가운데 큰 덩어리)을 넣은 그림
    closer = cv2.resize(room[120:1160, 60:660], (720, 1280))
    cv2.rectangle(closer, (200, 500), (520, 1280), (40, 40, 40), -1)
    same = tmp_path / "same.png"
    cv2.imwrite(str(same), closer)
    other = tmp_path / "other.png"
    _room(other, 2)
    assert plate_match(plate, same) >= PLATE_MIN_MATCH
    assert plate_match(plate, other) < PLATE_MIN_MATCH
    assert plate_match(plate, tmp_path / "missing.png") is None


def test_exit_door_must_open_to_the_outside():
    from app.videomake.stages.cut_images import DOOR_PROBLEM

    sb = _sb()
    cut = sb.cuts[0].model_copy(update={"image_prompt": "Camera faces the entrance side (the glass door). x"})
    assert DOOR_PROBLEM in image_problems(sb, cut, _seen(door_view="inside"))
    assert DOOR_PROBLEM not in image_problems(sb, cut, _seen(door_view="outside"))
    assert DOOR_PROBLEM not in image_problems(sb, sb.cuts[0], _seen(door_view="inside"))  # 문을 보는 컷이 아니면 묻지 않는다


def test_seated_people_are_told_to_stay_seated():
    from app.videomake.stages.video_render import stays_seated

    sb = _sb()
    seated = sb.cuts[0].model_copy(update={"image_prompt": "서연 sits at the table.",
                                           "motion_prompt": "서연 gives a small apologetic nod."})
    leaving = seated.model_copy(update={"motion_prompt": "They stand up and walk to the door."})
    assert stays_seated(seated) and not stays_seated(leaving)
    text = get_prompts().render("motion.j2", motion_prompt="x", shots=[], stays_seated=True, mood_line="",
                             dialogue=[], listening=False, ambient=False)
    assert "stays seated for the whole clip" in text


def test_blurred_band_at_the_bottom_is_found(tmp_path):
    import cv2

    from app.videomake.stages.cut_images import blurred_edge

    sharp = tmp_path / "sharp.png"
    room = _room(sharp, 3)
    smeared = room.copy()
    smeared[1150:] = cv2.GaussianBlur(room[1150:], (0, 0), 25)
    band = tmp_path / "band.png"
    cv2.imwrite(str(band), smeared)
    assert blurred_edge(sharp) == ""
    assert blurred_edge(band) == "bottom"
    assert blurred_edge(tmp_path / "missing.png") == ""


def test_location_sheet_must_start_from_the_master_view_unmirrored(tmp_path):
    import cv2
    import numpy as np

    from app.videomake.stages.reference_sheets import master_panel_match

    master = tmp_path / "master.png"
    room = _room(master, 4)
    def sheet(name, panel):
        grid = np.full((2560, 1440, 3), 200, np.uint8)
        grid[:1280, :720] = panel
        path = tmp_path / name
        cv2.imwrite(str(path), grid)
        return path
    same, flipped = master_panel_match(master, sheet("ok.png", room))
    assert same > flipped
    same, flipped = master_panel_match(master, sheet("mirror.png", room[:, ::-1]))
    assert flipped > same


def test_taking_off_a_coat_is_redrawn():
    from app.videomake.stages.cut_images import OUTFIT_PROBLEM, outfit_of, outfit_lines

    assert outfit_of("A woman in her fifties, short hair. She wears a beige trench coat over a lavender top.") \
        == "She wears a beige trench coat over a lavender top."
    assert outfit_of("A man, wearing a navy blazer and jeans.") == "wearing a navy blazer and jeans."
    sb = _sb()
    cut = sb.cuts[0]
    lines = outfit_lines(sb, cut)
    if not lines:  # 데모 인물의 외모에 옷이 없으면 검사할 것도 없다
        assert image_problems(sb, cut, _seen(outfit_mismatch=["아무개"])) == image_problems(sb, cut, _seen())
        return
    name = lines[0].split(": ", 1)[0]
    problems = image_problems(sb, cut, _seen(outfit_mismatch=[name]))
    assert any(p.startswith(OUTFIT_PROBLEM.split("{")[0] + "") or "must wear exactly this outfit" in p for p in problems)


def test_quoted_lines_in_the_diary_become_dialogue():
    from app.videomake.guardrails import lint_diary_quotes

    sb = _sb()
    said = [d.text for c in sb.cuts for d in c.dialogue]
    text = "오늘 엄마가 \"" + (said[0] if said else "잘 지냈어") + "\"라고 했다. 나는 \"엄마, 우리 자주 오자\"라고 말했다."
    missing = lint_diary_quotes(sb, text)
    assert [v.rule for v in missing] == ["일기 속 대사 누락"] * (1 if said else 2)
    assert "엄마, 우리 자주 오자" in missing[-1].detail
    assert lint_diary_quotes(sb, "따옴표 없는 일기") == []


def test_shopkeeper_speaks_over_the_protagonists_shoulder():
    from app.videomake.stages.cut_images import ots_partner

    payload = fake.demo_storyboard_payload(2)
    sb = _StoryboardDraft.model_validate(payload).to_storyboard()
    hero = sb.protagonist.name
    others = [c.name for c in sb.characters if c.name != hero]
    if not others:
        return
    keeper = others[0]
    first = sb.cuts[0].model_copy(update={"cast": [sb.cuts[0].cast[0].model_copy(update={"name": hero})]})
    talk = sb.cuts[1].model_copy(update={
        "location": first.location,
        "cast": [sb.cuts[1].cast[0].model_copy(update={"name": keeper, "position": "center"})],
        "dialogue": [sb.cuts[1].dialogue[0].model_copy(update={"speaker": keeper})] if sb.cuts[1].dialogue else [],
    })
    if not talk.dialogue:
        return
    sb2 = sb.model_copy(update={"cuts": [first, talk]})
    partner = ots_partner(sb2, talk)
    assert partner is not None and partner.name == hero


def test_partners_back_is_not_measured_as_the_speaker():
    from app.videomake.stages.cut_images import MEDIUM_PROBLEM, ots_partner

    sb = _sb()
    talk = next((c for c in sb.cuts if c.dialogue and ots_partner(sb, c)), None)
    if talk is None:
        return
    small_speaker = SeenFrame(people=[SeenPerson(gender="", height_ratio=0.6, from_behind=True),
                                      SeenPerson(gender="", height_ratio=0.25)],
                              looks_at_camera=False, foreground_back=True)
    assert MEDIUM_PROBLEM in image_problems(sb, talk, small_speaker)


def test_posture_props_and_sunlight_follow_the_scene():
    from app.videomake.stages.cut_images import SCENE_PROBLEM, SUN_PROBLEM, planned_sun

    sb = _sb()
    sunny = sb.cuts[0].model_copy(update={"image_prompt": "Weekend afternoon, warm sunlight. 서연 crouches."})
    night = sb.cuts[0].model_copy(update={"image_prompt": "Night, warm sunlight lamp."})
    assert planned_sun(sunny) and not planned_sun(night)
    problems = image_problems(sb, sunny, _seen(sunlight=False, scene_mismatch=["the basket is in her hands"]))
    assert SUN_PROBLEM in problems
    assert any(p.startswith(SCENE_PROBLEM) and "basket" in p for p in problems)
    assert SUN_PROBLEM not in image_problems(sb, sunny, _seen(sunlight=True))
