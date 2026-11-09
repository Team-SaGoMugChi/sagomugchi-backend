"""3. CutImageGenerator — 캐릭터 시트·장소 시트를 레퍼런스로 컷별 시작 프레임 생성.

반복과 검수는 전부 여기서 끝낸다. 컷 이미지 1장은 약 $0.045, 영상 1컷은 $0.80이다.
이미지를 17번 다시 뽑아도 영상 1컷보다 싸다.

레퍼런스는 그 컷 화면에 보이는 인물의 캐릭터 시트(위치 순서대로)와 그 장소의 장소 시트다.
같은 장소 컷의 첫 그림을 넘기던 방식은 그림 모델이 시점까지 베껴 폐기했다(reference_sheets.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path

from ..config import Settings
from ..errors import ProviderError
from ..job import JobStore
from ..models import Cut, Stage, Storyboard
from ..prompts import PromptLibrary
from ..providers.base import CastCheck, ImageProvider, LookProvider, PlaceCheck, SeenFrame

log = logging.getLogger(__name__)

_POSITION_ORDER = {"left": 0, "center": 1, "right": 2}


MEDIUM_MIN_HEIGHT = 0.35  # 허리 위 샷: 가장 큰 사람이 화면 높이의 이만큼은 넘어야 한다
SOLO_MIN_HEIGHT = 0.5  # 혼자 보이는 대사 컷(가슴 위): 이만큼은 넘어야 맞은편 자리가 화면에 안 들어온다
TINY_PERSON = 0.08  # 이보다 작은 사람은 배경 행인으로 본다


def image_problems(sb: Storyboard, cut: Cut, seen: SeenFrame) -> list[str]:
    """컷 그림이 컷 설계와 다른 점(영어 — 다시 그릴 때 그림 모델에 그대로 알려준다)."""
    from .dialogue_voice import voice_gender

    cast = sb.visible_cast(cut)
    # 어깨너머 대사 컷은 앞쪽 상대 뒷모습까지 사람으로 센다.
    partner = ots_partner(sb, cut)
    expected = [*cast, partner] if partner else cast
    people = [p for p in seen.people if p.height_ratio >= TINY_PERSON]
    problems = []
    # 장소 시트가 여러 칸짜리라 그림 모델이 칸 구성을 따라 그리는 일이 있다(2026-11 교문 컷 관측). 사람 수는 맞아 보여 따로 본다.
    if seen.split_frame:
        problems.append("The image is split into separate panels. Draw ONE continuous view from one camera, filling "
                        "the whole frame, with no panels, dividing lines or collage.")
    if len(people) < len(expected):
        problems.append(f"Only {len(people)} person(s) are visible but the scene needs {len(expected)}.")
    # 사람이 넘치는 경우: 화면 밖에 있어야 할 상대 대신 주인공 복제가 가장자리에 그려지는 일이 있다(2026-10 졸업식 컷 관측).
    # 잔치·식당처럼 손님이 있어야 하는 곳(background_people)은 배경 사람을 넘치는 사람으로 보지 않는다.
    # 등장인물 수를 넘는 사람을 모두 지우게 해서 잔치 연회장이 텅 비었다(2026-11 팔순 잔치).
    crowd = bool((place := sb.location(cut.location)) and place.background_people)
    if len(people) > len(expected) and not crowd:
        problems.append(f"{len(people)} people are visible but the scene has only {len(expected)}. Remove the extra "
                        "person completely; nobody else appears, not even partly at the edge of the frame.")
    if seen.duplicate_person:
        problems.append("The same person appears twice. Each person appears only once; never draw a copy of them.")
    if seen.unknown_person and not crowd:
        problems.append("Someone who is not in the cast is visible. Only the cast members appear.")
    # 손님이 있는 곳이라도 화면 끝에 잘린 낯선 사람은 지운다(2026-11 팔순 잔치 컷 6, 왼쪽 끝 흐린 얼굴 반쪽).
    if seen.cut_off_person:
        problems.append("A stranger is cut off at the edge of the frame close to the camera. Remove them; nobody "
                        "appears partly at the edge of the frame.")
    # 혼자 보이는 대사 컷: 상대 자리가 빈 의자로 보이면 상대가 사라진 것처럼 보인다(2026-11 카페 일기 컷 3~5).
    solo = solo_listener_side(sb, cut, cast) is not None
    if solo and seen.empty_seat:
        # 어깨너머 샷이면 상대가 그 자리에 뒷모습으로 앉아 있어야 한다. 예전 문구("상대 자리를 카메라 뒤로")를
        # 그대로 주면 어깨너머 지시와 반대라 그림 모델이 계속 빈 의자를 그렸다(2026-11 카페 컷 3~5).
        problems.append(OTS_EMPTY_SEAT_PROBLEM.format(name=partner.name) if partner else SOLO_EMPTY_SEAT_PROBLEM)
    # 빈 자리를 피하려다 상대(또는 엉뚱한 사람) 뒷모습을 앞에 걸쳐 그렸다(2026-11 카페 컷 3·5). 두 사람이
    # 보이면 Veo가 대사를 엉뚱한 입에 붙이고, 컷 5는 상대가 아닌 남자 뒷모습이었다.
    # 어깨너머 샷이면 앞쪽 뒷모습이 있어야 한다(상대가 사라진 것처럼 보이지 않게).
    if partner and seen.foreground_back is False:
        problems.append(f"{partner.name} must be seen from behind at the {partner.position} edge of the foreground "
                        "(back of the head and one shoulder), as in an over-the-shoulder shot.")
    elif solo and not partner and seen.foreground_back:
        problems.append(SOLO_BACK_PROBLEM)
    # 좌우: 창이 왼쪽 벽에 있는 카페에서 반대 방향을 보는 컷도 창이 화면 왼쪽에 그려져 방이 뒤집혀 보였다(2026-11 카페 2차).
    place = sb.location(cut.location)
    if place and (want := frame_window_side(place.description, planned_side(cut))) \
            and seen.window_side and seen.window_side != want:
        problems.append(WINDOW_PROBLEM.format(want=want))
    # 시간대: 밤 장면 사이에 한 컷만 창밖이 대낮으로 그려졌다(2026-11 자취방 일기 컷 3).
    want_time = planned_time(cut)
    if want_time and seen.time_of_day and seen.time_of_day != want_time:
        problems.append(TIME_PROBLEMS[want_time])
    # 출입문을 보는 컷: 문 너머가 또 다른 카페 안이면 나가는 장면이 들어오는 장면처럼 보인다(2026-11 카페 4차 컷 7).
    if planned_side(cut) == "entrance" and seen.door_view == "inside":
        problems.append(DOOR_PROBLEM)
    seats =dict(s.split(": ", 1) for s in seat_lines(sb, cut))
    for name in seen.wrong_seat:
        if name in seats:
            problems.append(f"{name} must be {seats[name]}, exactly where the location reference sheet shows it.")
    want = [voice_gender(f"{p.voice} {p.appearance}") for p in (sb.character(m.name) for m in expected) if p]
    for g, word in (("m", "man"), ("f", "woman")):
        # 성별을 모른다고 답한 사람은 어느 쪽으로든 셀 수 있다 — 확실히 다를 때만 틀렸다고 본다.
        need = want.count(g)
        got = sum(1 for p in people if p.gender in (g, ""))
        if need and got < need:
            problems.append(f"The scene needs {need} {word}(s) but {got} are drawn; draw each person exactly as their reference sheet.")
    # 허리 위 샷: 사람이 너무 작거나, 무릎 아래가 보이면(사실상 전신 샷) 다시 그린다.
    # Gemini의 키 어림값은 실제보다 크게 나와(수빈 실제 약 0.35 → 0.61) 다리가 보이는지를 함께 본다.
    # 등장인물만 본다(화면에서 가장 큰 사람부터 등장인물 수만큼). 다리가 안 보이는 뒤쪽 손님까지 세면
    # 전신으로 그린 컷도 통과했다(2026-11 팔순 잔치 개선판, 허리 위 컷 4개가 전부 전신).
    # 어깨너머 샷이면 앞쪽 뒷모습(상대)은 빼고 잰다. 상대의 큰 뒷모습을 말하는 사람으로 세어, 멀리 작게 앉은
    # 사람을 그린 그림이 통과했다(2026-11 칼국수집 8차 컷 6, 말하는 사람 약 0.25).
    facing = [p for p in people if not p.from_behind] if partner else people
    main = sorted(facing, key=lambda p: p.height_ratio, reverse=True)[: len(cast)]
    # 혼자 보이는 대사 컷은 더 가깝게(가슴 위) — 맞은편 자리가 화면에 들어오지 않게 한다.
    min_height = SOLO_MIN_HEIGHT if solo else MEDIUM_MIN_HEIGHT
    if (cut.camera_distance == "medium" or solo) and cast and main and (
        main[0].height_ratio < min_height or all(p.legs_visible for p in main)
    ):
        problems.append(MEDIUM_PROBLEM)
    if seen.looks_at_camera:
        problems.append(CAMERA_GAZE_PROBLEM)
    # 장소: 시트와 다른 곳처럼 그렸거나, 지시와 다른 벽을 보고 있으면 다시 그린다(2026-10 빵집 컷 관측).
    if seen.same_place is False:
        problems.append("This does not look like the same place as the location reference sheet. Keep its wall "
                        "and floor colors and materials, ceiling lights and furniture exactly the same.")
    for note in seen.scene_mismatch[:2]:
        problems.append(f"{SCENE_PROBLEM} {note}")
    if planned_sun(cut) and seen.sunlight is False:
        problems.append(SUN_PROBLEM)
    for name in seen.outfit_mismatch:
        if (outfit := dict(o.split(": ", 1) for o in outfit_lines(sb, cut)).get(name)):
            problems.append(OUTFIT_PROBLEM.format(name=name, outfit=outfit))
    want_side = planned_side(cut)
    if want_side and seen.facing and seen.facing != want_side:
        problems.append(f"{FACING_PROBLEM} {want_side} side of the place as written in SCENE, "
                        f"not the {seen.facing} side.")
    return problems


MEDIUM_PROBLEM = ("This must be a MEDIUM shot cropped at the waist: legs and feet must not be visible, "
                  "and the person must fill most of the frame height.")
FACING_PROBLEM = "The camera must face the"
SOLO_EMPTY_SEAT_PROBLEM = ("An empty chair or empty place is visible where the other person sits. Move the camera "
                           "close to this person, chest-up, from where the other person sits, so their seat and their "
                           "side of the table are behind the camera and not in the frame.")
OTS_EMPTY_SEAT_PROBLEM = ("An empty chair or empty place is visible. {name} sits in that place, seen from behind in the "
                          "foreground (back of the head and one shoulder); no chair or seat in the frame is empty.")
SOLO_BACK_PROBLEM = ("Someone's back, head or shoulder is in the foreground. This is not an over-the-shoulder "
                     "shot: only this one person is in the frame, and nobody else appears close to the camera "
                     "or at the edges.")
SCENE_PROBLEM = "Follow SCENE exactly for every person's posture and every object's place:"
SUN_PROBLEM = ("SCENE has warm direct sunlight: the light must be bright sun from one side with soft visible shadows, "
               "not a flat overcast day.")
_SUN = re.compile(r"\b(sunlight|sunny|sunshine|sunlit|direct sun|warm sun)\b", re.IGNORECASE)


def planned_sun(cut: Cut) -> bool:
    """그림 지시에 햇빛이 적혔나(밤 장면이면 아니다)."""
    return bool(_SUN.search(cut.image_prompt)) and not _NIGHT.search(cut.image_prompt)


OUTFIT_PROBLEM = ("{name} must wear exactly this outfit, with every layer on: {outfit} Nobody takes off or adds "
                  "a coat, jacket or other layer.")
CAMERA_GAZE_PROBLEM = "Someone looks into the camera. Nobody may look at the camera."
PLATE_PROBLEM = ("The background is not the seat plate. Behind the person, draw exactly the place in the empty "
                 "background plate: the same wall, windows, shelves and furniture in the same places. Only the "
                 "people are added; never turn the camera toward another wall.")
DOOR_PROBLEM = ("Through the entrance door you see another room. The entrance door leads OUTSIDE: through its glass "
                "only the street outside is visible, and the whole place is on this side of the door, behind the camera "
                "and around it.")
ROOM_PROBLEM = ("The place is arranged differently from the earlier shot of this same wall (the attached room "
                "image). Keep every counter, table, door and wall exactly where that shot shows them; only the "
                "people and the camera distance change.")
BLUR_PROBLEM = ("The {edge} edge of the picture is a blurred, smeared band. The whole frame is one sharp, continuous "
                "view right to its edges: no blurred strip, out-of-focus layer or smear at the top or bottom.")
BLUR_EDGE_RATIO = 0.01  # 끝 띠의 선명도가 가운데의 이만큼도 안 되면 번진 띠다(정상 그림 780장 중 가장 낮은 값 0.02)
PLATE_MIN_MATCH = 30  # 배경판과 맞는 특징점이 이보다 적으면 다른 벽을 그린 것이다(맞는 그림 63~524, 틀린 그림 7~18)
TIME_PROBLEMS = {
    "night": "It is night: the windows must show a dark night sky and the room is lit by its lamps, not daylight.",
    "day": "It is daytime: the windows must show daylight, not a dark night sky.",
}
_NIGHT = re.compile(r"\b(night|evening|dusk|after dark|midnight)\b", re.IGNORECASE)
_DAY = re.compile(r"\b(morning|afternoon|midday|noon|daylight|daytime|sunlight|sunny)\b", re.IGNORECASE)


def planned_time(cut: Cut) -> str:
    """image_prompt에 적힌 시간대: "night" / "day" / ""(안 적혔거나 둘 다 적힘)."""
    night, day = bool(_NIGHT.search(cut.image_prompt)), bool(_DAY.search(cut.image_prompt))
    return "night" if night and not day else "day" if day and not night else ""


def needs_redraw(cut: Cut, problems: list[str]) -> bool:
    """다시 그릴 만한 문제가 있는가.

    대사 없는 컷의 허리 위 샷이 전신으로 나온 것만 틀렸으면 그대로 쓴다(거리두기에 어긋나지 않고, 다시
    그려도 절반가량 또 전신이었다 — 2026-11 275컷 분석). 다른 벽을 보는 것도 한때 그대로 썼지만, 같은
    자리인데 컷마다 뒤 배경이 달라 장소가 바뀐 것처럼 보여서(2026-11 카페) 다시 그린다.
    """
    soft = [] if cut.dialogue else [MEDIUM_PROBLEM]
    return any(not any(p.startswith(s) for s in soft) for p in problems)


_SIDE = re.compile(r"camera faces the (entrance|far|left|right) side", re.IGNORECASE)


_SEAT = r"(?:sits|is seated|stays seated|remains seated)(?: (?:on the )?(?:left|right|center))? (at|beside|behind) (the [^,.;]+)"


def seat_lines(sb: Storyboard, cut: Cut) -> list[str]:
    """컷 지시(image_prompt)에 적힌, 보이는 인물의 앉는 자리. "할아버지: at the center honor table" 꼴."""
    lines = []
    for m in sb.visible_cast(cut):
        found = re.search(re.escape(m.name) + " " + _SEAT, cut.image_prompt)
        if found:
            lines.append(f"{m.name}: {found.group(1)} {found.group(2).strip()}")
    return lines


def plate_key(sb: Storyboard, cut: Cut) -> tuple[str, str, str] | None:
    """혼자 보이는 대사 컷의 배경판 열쇠(장소, 말하는 사람, 카메라 방향). 배경판을 쓰지 않는 컷이면 None.

    같은 자리에 앉은 사람의 대사 컷은 카메라 방향이 같으므로(guardrails.lint_dialogue_camera) 한 장을 함께 쓴다."""
    cast = sb.visible_cast(cut)
    side = planned_side(cut)
    if solo_listener_side(sb, cut, cast) is None or not side or not cut.location:
        return None
    return (cut.location, cast[0].name, side)


def seat_plate_prompt(sb: Storyboard, cut: Cut, *, prompts: PromptLibrary, aspect_ratio: str) -> str:
    """사람이 없는 배경판(그 사람이 앉는 자리에서 그 방향으로 본 모습) 프롬프트."""
    speaker = sb.visible_cast(cut)[0].name
    seats = dict(s.split(": ", 1) for s in seat_lines(sb, cut))
    camera = cut.image_prompt.split(".")[0].strip() + "."
    return prompts.render(
        "seat_plate.j2",
        location=sb.location(cut.location),
        camera=camera,
        seat=(f"the seat {seats[speaker]}" if speaker in seats else f"the seat where {speaker} sits")
        .replace(speaker, "the person"),
        side=planned_side(cut),
        time_of_day=planned_time(cut),
        sunny=planned_sun(cut),
        aspect_ratio=aspect_ratio,
        style_block=prompts.style_block,
    )


# 장소 벽 → 그 벽의 창이 화면 어느 쪽에 오는가(카메라가 보는 방향별). 좌우가 뒤집힌 그림을 잡는다.
_WINDOW_FRAME_SIDE = {
    ("left", "far"): "left", ("left", "entrance"): "right",
    ("right", "far"): "right", ("right", "entrance"): "left",
    ("far", "left"): "right", ("far", "right"): "left",
    ("entrance", "left"): "left", ("entrance", "right"): "right",
}
_WALL = re.compile(r"\b(Entrance|Far|Left|Right) side:", re.IGNORECASE)
WINDOW_PROBLEM = ("The windows are on the wrong side: in this view they must be on the {want} side of the frame. "
                  "The room is never mirrored; keep every wall where the location sheet shows it.")


def frame_window_side(description: str, facing: str) -> str:
    """장소 설명에서 창이 있는 벽이 하나면, 카메라가 facing 쪽을 볼 때 창이 화면 어느 쪽에 오는지. 모르면 ""."""
    marks = list(_WALL.finditer(description))
    # "Left side: …" 부터 다음 "… side:" 앞까지가 그 벽 설명이다.
    walls = [
        m.group(1).lower() for k, m in enumerate(marks)
        if "window" in description[m.end(): marks[k + 1].start() if k + 1 < len(marks) else None].lower()
    ]
    if len(walls) != 1 or not facing:
        return ""
    return _WINDOW_FRAME_SIDE.get((walls[0], facing), "")


def planned_side(cut: Cut) -> str:
    """image_prompt 첫머리의 "Camera faces the left side ..."에서 방향을 읽는다. 없으면 ""."""
    m = _SIDE.search(cut.image_prompt)
    return m.group(1).lower() if m else ""


async def generate_cut_images(
    sb: Storyboard,
    *,
    sheet: Path,
    image: ImageProvider,
    prompts: PromptLibrary,
    settings: Settings,
    job: JobStore,
    character_sheets: dict[str, Path] | None = None,
    location_sheets: dict[str, Path] | None = None,
    only: set[int] | None = None,
    force: bool = False,
    look: LookProvider | None = None,
) -> dict[int, Path]:
    """sheet: 주인공 캐릭터 시트. character_sheets: 조연 이름 → 시트. location_sheets: 장소 이름 → 시트."""
    sheets = {sb.protagonist.name: sheet, **(character_sheets or {})}
    location_sheets = location_sheets or {}
    targets = [c for c in sb.cuts if only is None or c.index in only]
    sem = asyncio.Semaphore(settings.image_concurrency)
    started = time.perf_counter()

    async def one(cut) -> tuple[int, Path]:
        dest = job.cut_image(cut.index)
        # 검사가 끝나지 않은 그림(작업이 그리는 도중 멈춤)은 재사용하지 않는다 — 다시 시작하면 검사 없이 영상이 됐다
        # (2026-11 칼국수집 컷 4·6).
        checked = look is None or (job.cut_dir(cut.index) / "image_check.json").exists()
        if dest.exists() and not force and checked:
            log.info("컷 %d 이미지 캐시 재사용", cut.index)
            return cut.index, dest
        loc = sb.location(cut.location)
        place_sheet = location_sheets.get(cut.location) if cut.location else None
        place = (PlaceCheck(sheet=place_sheet, description=loc.description, seats=seat_lines(sb, cut))
                 if loc and place_sheet else None)
        cast_check = CastCheck(people=check_people(sb, cut), outfits=outfit_lines(sb, cut), scene=cut.image_prompt)
        # 혼자 보이는 대사 컷에는 앞 컷 그림을 참고로 주지 않는다. 두 사람 컷(같은 순간)이나 같은 벽 컷을 주면
        # 그 각도를 따라 그려, 상대 자리가 빈 의자로 보였다(2026-11 카페 일기 컷 3~5).
        solo = solo_listener_side(sb, cut, sb.visible_cast(cut)) is not None
        moment_image = None
        room = None if solo else room_shot(sb, cut)
        room_image = job.cut_image(room) if room else None
        # 혼자 보이는 대사 컷은 그 자리의 배경판(사람 없는 배경)을 따라 그린다 — 같은 자리면 배경이 같다.
        key = plate_key(sb, cut)
        plate = await plates[key] if key in plates else None
        panel = side_panel(job, place_sheet, planned_side(cut)) if place_sheet and not plate else None
        prompt, references = cut_image_request(
            sb,
            cut,
            sheets=sheets,
            location_sheets=location_sheets,
            prompts=prompts,
            aspect_ratio=settings.aspect_ratio,
            moment_image=moment_image if moment_image and moment_image.exists() else None,
            room_image=room_image if room_image and room_image.exists() else None,
            seat_plate=plate if plate and plate.exists() else None,
            side_panel=panel,
        )
        async def draw(text: str, tag: str) -> None:
            async with sem:
                result = await image.generate(
                    prompt=text,
                    dest=dest,
                    references=references,
                    aspect_ratio=settings.aspect_ratio,
                    image_size=settings.image_size,
                )
            log.info("컷 %d 이미지 %.1fs / $%s", cut.index, result.elapsed_s, result.cost_usd)
            job.record_cost(f"cut{cut.index}_image{tag}", result.cost_usd)

        try:
            await draw(prompt, "")
        except ProviderError as exc:  # 그림 없는 답은 같은 요청으로 다시 하면 대개 나온다
            log.warning("컷 %d 그림이 안 나와 한 번 더 그린다: %s", cut.index, exc)
            await draw(prompt, "_again")
        # 그림 검사: 사람 수·성별·허리 위 크기·카메라 응시. 틀리면 무엇이 틀렸는지 알려주고 다시 그린다.
        checks = []
        for attempt in range(1, settings.image_check_retries + 2):
            if look is None:
                break
            seen = None
            # 검사가 한 번 실패했다고 검사 없이 통과시키지 않는다 — 한 번 더 묻는다.
            for _ in range(LOOK_TRIES):
                try:
                    seen = await look.look(image=dest, place=place, cast=cast_check)
                    break
                except Exception as exc:
                    log.warning("컷 %d 그림 확인 실패: %s", cut.index, exc)
            if seen is None:
                log.warning("컷 %d 그림을 확인하지 못해 그대로 쓴다", cut.index)
                break
            problems = image_problems(sb, cut, seen)
            # 배경판을 따라 그린 컷은 배경판과 직접 맞춰 본다. 그림 검사(Gemini)는 어깨너머 샷의 방향을 자주
            # 틀려, 벽돌벽을 맞게 그린 그림을 떨어뜨리고 창가를 그린 그림을 골랐다(2026-11 카페 3차 컷 5).
            # 같은 벽을 보는 앞 컷이 있으면 그 그림과 맞춰 본다 — 참고로 줬는데도 카운터를 가게 한가운데로
            # 옮겨 그려 다른 가게처럼 보였다(2026-11 칼국수집 컷 5: 같은 벽 컷과 맞는 점 6~8, 맞는 컷끼리 417).
            ref = plate if plate and plate.exists() else room_image if room_image and room_image.exists() else None
            match = await asyncio.to_thread(plate_match, ref, dest) if ref else None
            if match is not None:
                problems = [p for p in problems if not p.startswith((FACING_PROBLEM, WINDOW_PROBLEM[:30]))]
                if match < PLATE_MIN_MATCH:
                    problems.append(PLATE_PROBLEM if ref == plate else ROOM_PROBLEM)
            # 위·아래 끝이 뿌옇게 번진 띠로 그려지는 일이 있다(2026-11 칼국수집 컷 5, 780장 중 1장).
            if (edge := await asyncio.to_thread(blurred_edge, dest)):
                problems.append(BLUR_PROBLEM.format(edge=edge))
            checks.append({"attempt": attempt, "problems": problems, "plate_match": match, "seen": seen.model_dump()})
            shutil.copy2(dest, job.cut_dir(cut.index) / f"attempt{attempt}.png")
            if not problems or attempt > settings.image_check_retries or not needs_redraw(cut, problems):
                break
            log.warning("컷 %d 그림 다시 그림(%d): %s", cut.index, attempt, problems)
            try:
                await draw(prompt + "\n\nTHE PREVIOUS ATTEMPT WAS WRONG. Fix this:\n- " + "\n- ".join(problems),
                           f"_retry{attempt}")
            except ProviderError as exc:
                # 다시 그리기 한 장이 안 나왔다고(그림 없는 답) 작업 전체를 멈추지 않는다 — 그린 그림 중에서 고른다
                # (2026-11 칼국수집, 두 번 연달아 이 한 장 때문에 처음부터 다시 돌았다).
                log.warning("컷 %d 다시 그리기 실패 — 앞 그림 중에서 고른다: %s", cut.index, exc)
                shutil.copy2(job.cut_dir(cut.index) / f"attempt{attempt}.png", dest)
                break
        # 다시 그리기를 다 써도 문제가 남으면 마지막 그림이 아니라 문제가 가장 적은 그림을 쓴다.
        # 마지막 그림이 오히려 더 나쁜 경우가 있었다(2026-11 카페 컷 3·4·5, 문제 3~5개 남은 채 사용).
        if len(checks) > 1:
            # 문제 수가 같으면 앞 그림을 쓴다 — "고쳐라" 지시가 쌓인 뒤 그림이 오히려 방을 다르게 지어낸 적이 있다
            # (2026-11 카페 컷 7: 1·2번째는 같은 카페, 3번째만 조명이 다른 방).
            # 대사 컷에서 말하는 사람이 작게 나온 그림은 문제 수가 같아도 뒤로 미룬다. 배경판과 가장 닮은 그림이
            # 사람이 자리에 없어 배경판이 그대로 보이는 그림이었고, 그 그림으로 영상을 만들자 Veo가 멀리 있던
            # 사람을 일으켜 걸어오게 했다(2026-11 카페 6차 컷 4).
            best = min(checks, key=lambda c: (len(c["problems"]),
                                              bool(cut.dialogue) and MEDIUM_PROBLEM in c["problems"],
                                              CAMERA_GAZE_PROBLEM in c["problems"],
                                              -(c["plate_match"] or 0), c["attempt"]))
            if best is not checks[-1]:
                shutil.copy2(job.cut_dir(cut.index) / f"attempt{best['attempt']}.png", dest)
                log.info("컷 %d: %d번째 그림이 문제가 가장 적어 그것을 쓴다", cut.index, best["attempt"])
            for c in checks:
                c["chosen"] = c is best
        if checks:
            (job.cut_dir(cut.index) / "image_check.json").write_text(
                json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
        # 이미지를 새로 뽑았으면 기존 승인은 무효다.
        job.unapprove({cut.index})
        return cut.index, dest

    # 대사 컷 배경판: 자리·방향마다 한 장. 컷 그림보다 먼저(필요한 컷이 기다린다) 그린다.
    plates: dict[tuple[str, str, str], asyncio.Future] = {}
    for c in targets:
        key = plate_key(sb, c)
        if key is None or key in plates or not location_sheets.get(c.location):
            continue
        dest_plate = job.dir / "plates" / f"{_slug(key)}.png"
        plates[key] = asyncio.ensure_future(_draw_plate(
            sb, c, dest_plate, image=image, prompts=prompts, settings=settings, job=job,
            location_sheet=location_sheets[c.location], sem=sem, force=force, look=look,
        ))

    # 참고할 그림을 먼저 그린다: 같은 벽을 보는 첫 컷 → 그 방을 참고하는 컷.
    room_cuts = [c for c in targets if solo_listener_side(sb, c, sb.visible_cast(c)) is None
                 and room_shot(sb, c) is not None]
    first = [c for c in targets if c not in room_cuts]
    pairs = []
    for wave in (first, room_cuts):
        pairs += await asyncio.gather(*(one(c) for c in wave))
    await asyncio.to_thread(match_light, sb, job, {i for i, _ in pairs})
    job.record_stage(
        Stage.CUT_IMAGES,
        elapsed_s=time.perf_counter() - started,
        cuts=[i for i, _ in pairs],
    )
    return dict(pairs)


def plate_match(plate: Path, image: Path) -> int | None:
    """배경판과 컷 그림에서 같은 자리로 이어지는 특징점 수(SIFT + RANSAC). 확대·사람이 달라도 같은 벽이면 많다.

    읽지 못하면 None — 검사 없이 넘어간다."""
    try:
        import cv2
        import numpy as np

        def load(path: Path):
            im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            h, w = im.shape
            return cv2.resize(im, (int(w * 800 / h), 800))

        sift = cv2.SIFT_create(3000)
        kp_a, des_a = sift.detectAndCompute(load(plate), None)
        kp_b, des_b = sift.detectAndCompute(load(image), None)
        if des_a is None or des_b is None or len(kp_a) < 2 or len(kp_b) < 2:
            return 0
        good = [m for m, n in (p for p in cv2.BFMatcher().knnMatch(des_a, des_b, k=2) if len(p) == 2)
                if m.distance < 0.75 * n.distance]
        if len(good) < 8:
            return 0
        src = np.float32([kp_a[m.queryIdx].pt for m in good])
        dst = np.float32([kp_b[m.trainIdx].pt for m in good])
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
        return int(mask.sum()) if mask is not None else 0
    except Exception as exc:
        log.warning("배경판 비교 실패: %s", exc)
        return None


def blurred_edge(image: Path) -> str:
    """그림 위·아래 10% 띠가 가운데보다 아주 흐리면 그 쪽("top"/"bottom"), 아니면 ""."""
    try:
        import cv2

        im = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
        h, w = im.shape
        im = cv2.resize(im, (int(w * 800 / h), 800))

        def sharp(a) -> float:
            return float(cv2.Laplacian(a, cv2.CV_64F).var())

        middle = sharp(im[240:560])
        if middle <= 0:
            return ""
        for edge, band in (("bottom", im[720:]), ("top", im[:80])):
            if sharp(band) / middle < BLUR_EDGE_RATIO:
                return edge
    except Exception as exc:
        log.warning("끝 띠 확인 실패: %s", exc)
    return ""


LIGHT_GAIN_RANGE = (0.85, 1.18)  # 색 맞추기로 한 채널을 이만큼까지만 바꾼다(그림을 망치지 않게)
LIGHT_TOLERANCE = 0.06  # 이보다 작게 다르면 그대로 둔다


def _mean_rgb(path: Path) -> tuple[float, float, float] | None:
    from .compose import _ffmpeg

    proc = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", str(path), "-vf", "scale=1:1:flags=area", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=False, stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0 or len(proc.stdout) < 3:
        return None
    r, g, b = proc.stdout[:3]
    return float(r), float(g), float(b)


def match_light(sb: Storyboard, job: JobStore, drawn: set[int]) -> None:
    """같은 장소 컷의 밝기·색을 그 장소 첫 컷에 맞춘다(그림 파일 자체를 고친다, 비용 없음).

    같은 카페인데 두 사람 컷은 어둡고 푸르고, 대사 컷은 밝고 노랗게 그려져 컷마다 조명이 바뀐 것처럼
    보였다(2026-11 카페 2차). 채널별 평균을 첫 컷에 맞추되 LIGHT_GAIN_RANGE 안에서만 바꾼다."""
    from .compose import _ffmpeg

    first: dict[str, int] = {}
    for c in sb.cuts:
        if c.location:
            first.setdefault(c.location, c.index)
    for c in sb.cuts:
        ref_index = first.get(c.location or "")
        if c.index not in drawn or ref_index is None or ref_index == c.index:
            continue
        ref, cur = _mean_rgb(job.cut_image(ref_index)), _mean_rgb(job.cut_image(c.index))
        if not ref or not cur or min(cur) <= 0:
            continue
        lo, hi = LIGHT_GAIN_RANGE
        gains = [min(max(rv / cv, lo), hi) for rv, cv in zip(ref, cur)]
        if max(abs(g - 1) for g in gains) < LIGHT_TOLERANCE:
            continue
        src = job.cut_image(c.index)
        raw = src.with_name("image_before_light.png")
        shutil.copy2(src, raw)
        proc = subprocess.run(
            [_ffmpeg(), "-v", "error", "-y", "-i", str(raw), "-vf",
             f"colorchannelmixer=rr={gains[0]:.3f}:gg={gains[1]:.3f}:bb={gains[2]:.3f}", str(src)],
            capture_output=True, check=False, stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            shutil.copy2(raw, src)
            continue
        log.info("컷 %d 밝기·색을 컷 %d에 맞춤 (R×%.2f G×%.2f B×%.2f)", c.index, ref_index, *gains)


LOOK_TRIES = 2  # 그림 검사가 실패하면 한 번 더 묻는다

# 장소 시트의 2×2 칸 → 카메라가 보는 벽(location_sheet.j2의 칸 배치와 같다). (가로, 세로) 시작 위치.
_SHEET_PANELS = {"far": (0, 0), "entrance": (1, 0), "left": (0, 1), "right": (1, 1)}


def side_panel(job: JobStore, location_sheet: Path, side: str) -> Path | None:
    """장소 시트에서 그 방향(벽) 칸만 잘라 낸 그림. 컷 그림이 그 벽을 배경으로 그대로 쓰게 한다(비용 없음).

    시트 전체만 주면 그림 모델이 방을 그럴듯하게 다시 지어내 컷마다 가구 배치가 달라졌다(2026-11 카페·삼겹살집)."""
    if side not in _SHEET_PANELS or not location_sheet.exists():
        return None
    dest = job.dir / "plates" / f"side_{location_sheet.stem}_{side}.png"
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    col, row = _SHEET_PANELS[side]
    from .compose import _ffmpeg

    proc = subprocess.run(
        [_ffmpeg(), "-v", "error", "-y", "-i", str(location_sheet),
         "-vf", f"crop=iw/2:ih/2:{col}*iw/2:{row}*ih/2", str(dest)],
        capture_output=True, check=False, stdin=subprocess.DEVNULL,
    )
    return dest if proc.returncode == 0 and dest.exists() else None


def _slug(key: tuple[str, str, str]) -> str:
    import hashlib

    return hashlib.sha1("|".join(key).encode("utf-8")).hexdigest()[:10]


async def _draw_plate(
    sb: Storyboard, cut: Cut, dest: Path, *, image: ImageProvider, prompts: PromptLibrary,
    settings: Settings, job: JobStore, location_sheet: Path, sem: asyncio.Semaphore, force: bool,
    look: LookProvider | None = None,
) -> Path | None:
    """대사 컷 배경판을 그린다(그림 1장 값). 실패하면 None — 배경판 없이 그린다.

    배경판도 지시한 벽을 보는지 확인한다. 두 사람 배경판이 모두 "가게를 길게 바라보는 같은 구도"로 그려져
    마주 앉은 두 사람이 같은 쪽을 보는 것처럼 보였다(2026-11 카페 2차). 사람이 없어 방향 검사가 정확하다."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    side = planned_side(cut)
    loc = sb.location(cut.location)
    base = seat_plate_prompt(sb, cut, prompts=prompts, aspect_ratio=settings.aspect_ratio)
    references = [location_sheet, *([panel] if (panel := side_panel(job, location_sheet, side)) else [])]
    text = base
    attempts: list[tuple[int, Path]] = []  # (문제 수, 그림)
    for attempt in range(1, settings.image_check_retries + 2):
        target = dest.with_name(f"{dest.stem}_try{attempt}.png")
        try:
            async with sem:
                result = await image.generate(
                    prompt=text, dest=target, references=references,
                    aspect_ratio=settings.aspect_ratio, image_size=settings.image_size,
                )
        except Exception as exc:
            log.warning("컷 %d 배경판을 그리지 못했다: %s", cut.index, exc)
            break
        job.record_cost(f"plate_cut{cut.index}_try{attempt}", result.cost_usd)
        problems: list[str] = []
        if look is not None and loc is not None:
            try:
                seen = await look.look(image=target, place=PlaceCheck(sheet=location_sheet, description=loc.description))
                if side and seen.facing and seen.facing != side:
                    problems.append(f"{FACING_PROBLEM} {side} side of the place, not the {seen.facing} side. "
                                    f"The {side} side fills the background straight ahead.")
                if (want := frame_window_side(loc.description, side)) and seen.window_side \
                        and seen.window_side != want:
                    problems.append(WINDOW_PROBLEM.format(want=want))
            except Exception as exc:
                log.warning("컷 %d 배경판 확인 실패: %s", cut.index, exc)
        attempts.append((len(problems), target))
        if not problems:
            break
        log.warning("컷 %d 배경판 다시 그림(%d): %s", cut.index, attempt, problems)
        text = base + "\n\nTHE PREVIOUS ATTEMPT WAS WRONG. Fix this:\n- " + "\n- ".join(problems)
    if not attempts:
        return None
    best = min(attempts, key=lambda a: a[0])[1]  # 같으면 앞 그림
    shutil.copy2(best, dest)
    log.info("컷 %d 배경판 완성 (%d번 그림)", cut.index, len(attempts))
    return dest


def voice_off_screen(sb: Storyboard, cut: Cut) -> bool:
    """대사 컷인데 말하는 사람이 모두 화면에 없다(전화 속 목소리 등).

    이런 컷은 Veo에게 말소리를 시키지 않는다 — 말소리를 만들면 화면에 보이는 사람의 입을
    그 소리에 맞춰 움직였다(듣기만 해야 하는 사람이 말하는 것처럼 보임). 목소리는 더빙이 넣는다."""
    if not cut.is_dialogue:
        return False
    shown = {m.name for m in sb.visible_cast(cut)}
    return all(line.speaker not in shown for line in cut.dialogue)


def mood_subject(sb: Storyboard, cut: Cut) -> str:
    """감정(표정·자세) 지시를 받을 사람 — 그 컷 화면에 보이는 사람. 주인공이 보이면 주인공,
    주인공 없이 다른 사람만 보이면 그 사람이다. 아무도 없으면 주인공(장면 분위기).
    늘 주인공 이름을 쓰면 지수 혼자 나오는 컷에 "민서: hurt"처럼 화면에 없는 사람을 지시했다."""
    names = [m.name for m in sb.visible_cast(cut)]
    if not names or sb.protagonist.name in names:
        return sb.protagonist.name
    return names[0]


def solo_listener_side(sb: Storyboard, cut: Cut, cast: list) -> str | None:
    """대사 컷에 말하는 사람 혼자 보이면, 화면 밖 상대가 있는 쪽(시선 방향). 아니면 None.
    화면 왼쪽에 있는 사람은 오른쪽을 본다. 가운데면 오른쪽으로 둔다.

    상대가 그 장소에 실제로 있을 때만이다 — 같은 장소의 다른 컷에 다른 사람이 함께 보인다.
    전화 통화처럼 혼자 있는 장면에 "화면 밖 상대"를 쓰면 그림 모델이 화면 끝에 엉뚱한
    사람의 뒷모습을 그렸다."""
    if not cut.is_dialogue or len(cast) != 1:
        return None
    speaker = cast[0].name
    if speaker not in {line.speaker for line in cut.dialogue}:
        return None
    present = any(
        m.name != speaker
        for c in sb.cuts
        if c.location == cut.location
        for m in c.cast
    )
    if not present:
        return None
    return "left" if cast[0].position == "right" else "right"


def check_people(sb: Storyboard, cut: Cut) -> list[str]:
    """그림·영상 검사에 알려 줄 그 컷의 사람들(짧은 외모). 어깨너머 상대는 "뒷모습"으로 덧붙인다."""
    people = [
        (p.appearance.split(".")[0].strip() if (p := sb.character(m.name)) else m.name) for m in sb.visible_cast(cut)
    ]
    partner = ots_partner(sb, cut)
    if partner:
        p = sb.character(partner.name)
        look = p.appearance.split(".")[0].strip() if p else partner.name
        people.append(f"{look} (seen from behind in the foreground, face not visible)")
    return people


def outfit_of(appearance: str) -> str:
    """외모 묘사에서 옷차림 부분. "She wears ..." 문장이 있으면 그 문장부터, 없으면 "wearing ..." 뒤."""
    m = re.search(r"\b(?:He|She|They) wears?\b.*", appearance) or re.search(r"\bwearing\b.*", appearance)
    return m.group(0).strip() if m else ""


def outfit_lines(sb: Storyboard, cut: Cut) -> list[str]:
    """그림 검사에 줄 "이름: 옷차림". 화면에 얼굴이 보이는 사람만(어깨너머 뒷모습은 옷이 잘 안 보인다)."""
    return [f"{m.name}: {o}" for m in sb.visible_cast(cut)
            if (p := sb.character(m.name)) and (o := outfit_of(p.appearance))]


def ots_partner(sb: Storyboard, cut: Cut):
    """혼자 보이는 대사 컷에서 앞쪽에 뒷모습으로 걸치는 상대(어깨너머 샷). 아니면 None.

    상대를 화면 밖으로 빼라고 하면 그림 모델이 빈 의자를 그리거나 상대를 걸쳐 그려 대화하던 사람이 사라진 것처럼
    보였다(2026-11 카페). 드라마처럼 상대의 뒷모습을 일부러 보여 준다 — 얼굴·입이 안 보여 대사가 엉뚱한 입에
    붙지 않는다. 상대는 같은 장소에서 말하는 사람과 함께 보인 가장 가까운 컷(앞 컷 우선)의 다른 사람이다."""
    from ..models import CastMember

    side = solo_listener_side(sb, cut, sb.visible_cast(cut))
    if side is None:
        return None
    speaker = cut.cast[0].name
    together = [
        c for c in sb.cuts
        if c.index != cut.index and c.location == cut.location and len(c.cast) > 1
        and speaker in {m.name for m in c.cast}
    ]
    if not together:
        # 함께 보인 컷이 없는 사람(가게 주인 등)은 그 장소의 주인공에게 말한다. 상대를 정하지 않으면 그림 모델이
        # 모르는 남자의 뒷모습을 그렸다(2026-11 칼국수집 7차 컷 2).
        here = [m.name for c in sb.cuts if c.location == cut.location for m in c.cast if m.name != speaker]
        if not here:
            return None
        other = sb.protagonist.name if sb.protagonist.name in here else here[0]
        return CastMember(name=other, position=side)
    near = min(together, key=lambda c: (c.index > cut.index, abs(c.index - cut.index)))
    other = next(m.name for m in near.cast if m.name != speaker)
    return CastMember(name=other, position=side)


def room_shot(sb: Storyboard, cut: Cut) -> int | None:
    """같은 장소에서 같은 벽을 보는 첫 컷 — 천장·조명·벽을 맞추는 참고 그림. 없거나 자기가 첫 컷이면 None.

    장소 시트만으로는 컷마다 천장 조명 모양이 달라졌다(2026-11 팔순 잔치 연회장).
    다른 벽을 보는 컷에 참고 그림을 주면 "각도는 따라 하지 말라"고 해도 그 각도를 그대로 따라 그려
    8컷 중 7컷이 같은 화면이 됐다(2026-11 팔순 잔치 개선판). 같은 벽을 볼 때만 준다.
    """
    side = planned_side(cut)
    first = next((c for c in sb.cuts if c.location == cut.location and planned_side(c) == side), None)
    return None if not side or first is None or first.index == cut.index else first.index


def moment_shot(sb: Storyboard, cut: Cut) -> int | None:
    """혼자 나오는 대사 컷이 참고할 같은 순간의 컷 — 같은 장소에서 말하는 사람이 다른 사람과
    함께 보이는 가장 가까운 컷(앞 컷 우선). 테이블·의자·컵·옷을 맞추는 데만 쓴다.
    텍스트만으로는 한 사람 컷의 테이블 모양·색이 두 사람 컷과 달라졌다."""
    if solo_listener_side(sb, cut, sb.visible_cast(cut)) is None:
        return None
    speaker = cut.cast[0].name
    candidates = [
        c for c in sb.cuts
        if c.index != cut.index and c.location == cut.location
        and len(c.cast) > 1 and speaker in {m.name for m in c.cast}
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c.index > cut.index, abs(c.index - cut.index))).index


def cut_image_request(
    sb: Storyboard,
    cut: Cut,
    *,
    sheets: dict[str, Path],
    location_sheets: dict[str, Path],
    prompts: PromptLibrary,
    aspect_ratio: str,
    camera_distance: str | None = None,
    thumbnail: bool = False,
    moment_image: Path | None = None,
    room_image: Path | None = None,
    seat_plate: Path | None = None,
    side_panel: Path | None = None,
) -> tuple[str, list[Path]]:
    """컷 하나를 그릴 프롬프트와 레퍼런스(화면 속 인물 시트 → 장소 시트).

    컷 그림과 썸네일(가로 구도)이 같은 규칙으로 그려지도록 한곳에 둔다.
    """
    cast = sorted(sb.visible_cast(cut), key=lambda m: _POSITION_ORDER[m.position])
    partner = ots_partner(sb, cut)
    # 어깨너머 상대도 옷·머리가 같아야 해서 시트를 함께 준다(앞쪽 뒷모습).
    people = [m for m in [*cast, *([partner] if partner else [])] if m.name in sheets]
    place_sheet = location_sheets.get(cut.location)
    references = [sheets[m.name] for m in people] + ([place_sheet] if place_sheet else [])
    if room_image is not None:
        references.append(room_image)
    if moment_image is not None:
        references.append(moment_image)
    if seat_plate is not None:
        references.append(seat_plate)
    if side_panel is not None:
        references.append(side_panel)
    prompt = prompts.render(
        "cut_image.j2",
        people=people,
        cast=cast,
        solo_side=solo_listener_side(sb, cut, cast),
        partner=partner,
        location=sb.location(cut.location),
        has_location_sheet=place_sheet is not None,
        has_moment_image=moment_image is not None,
        has_room_image=room_image is not None,
        has_seat_plate=seat_plate is not None,
        has_side_panel=side_panel is not None,
        thumbnail=thumbnail,
        image_prompt=cut.image_prompt,
        camera_distance=camera_distance or cut.camera_distance,
        aspect_ratio=aspect_ratio,
        style_block=prompts.style_block,
        mood_block=prompts.render(
            "mood.j2", mood=cut.mood, name=mood_subject(sb, cut), part="image"
        ),
    )
    return prompt, references
