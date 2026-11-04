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
import time
from pathlib import Path

from ..config import Settings
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
    people = [p for p in seen.people if p.height_ratio >= TINY_PERSON]
    problems = []
    # 장소 시트가 여러 칸짜리라 그림 모델이 칸 구성을 따라 그리는 일이 있다(2026-11 교문 컷 관측). 사람 수는 맞아 보여 따로 본다.
    if seen.split_frame:
        problems.append("The image is split into separate panels. Draw ONE continuous view from one camera, filling "
                        "the whole frame, with no panels, dividing lines or collage.")
    if len(people) < len(cast):
        problems.append(f"Only {len(people)} person(s) are visible but the scene needs {len(cast)}.")
    # 사람이 넘치는 경우: 화면 밖에 있어야 할 상대 대신 주인공 복제가 가장자리에 그려지는 일이 있다(2026-10 졸업식 컷 관측).
    # 잔치·식당처럼 손님이 있어야 하는 곳(background_people)은 배경 사람을 넘치는 사람으로 보지 않는다.
    # 등장인물 수를 넘는 사람을 모두 지우게 해서 잔치 연회장이 텅 비었다(2026-11 팔순 잔치).
    crowd = bool((place := sb.location(cut.location)) and place.background_people)
    if len(people) > len(cast) and not crowd:
        problems.append(f"{len(people)} people are visible but the scene has only {len(cast)}. Remove the extra "
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
        problems.append(SOLO_EMPTY_SEAT_PROBLEM)
    # 빈 자리를 피하려다 상대(또는 엉뚱한 사람) 뒷모습을 앞에 걸쳐 그렸다(2026-11 카페 컷 3·5). 두 사람이
    # 보이면 Veo가 대사를 엉뚱한 입에 붙이고, 컷 5는 상대가 아닌 남자 뒷모습이었다.
    if solo and seen.foreground_back:
        problems.append(SOLO_BACK_PROBLEM)
    # 시간대: 밤 장면 사이에 한 컷만 창밖이 대낮으로 그려졌다(2026-11 자취방 일기 컷 3).
    want_time = planned_time(cut)
    if want_time and seen.time_of_day and seen.time_of_day != want_time:
        problems.append(TIME_PROBLEMS[want_time])
    seats = dict(s.split(": ", 1) for s in seat_lines(sb, cut))
    for name in seen.wrong_seat:
        if name in seats:
            problems.append(f"{name} must be {seats[name]}, exactly where the location reference sheet shows it.")
    want = [voice_gender(f"{p.voice} {p.appearance}") for p in (sb.character(m.name) for m in cast) if p]
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
    main = sorted(people, key=lambda p: p.height_ratio, reverse=True)[: len(cast)]
    # 혼자 보이는 대사 컷은 더 가깝게(가슴 위) — 맞은편 자리가 화면에 들어오지 않게 한다.
    min_height = SOLO_MIN_HEIGHT if solo else MEDIUM_MIN_HEIGHT
    if (cut.camera_distance == "medium" or solo) and cast and main and (
        main[0].height_ratio < min_height or all(p.legs_visible for p in main)
    ):
        problems.append(MEDIUM_PROBLEM)
    if seen.looks_at_camera:
        problems.append("Someone looks into the camera. Nobody may look at the camera.")
    # 장소: 시트와 다른 곳처럼 그렸거나, 지시와 다른 벽을 보고 있으면 다시 그린다(2026-10 빵집 컷 관측).
    if seen.same_place is False:
        problems.append("This does not look like the same place as the location reference sheet. Keep its wall "
                        "and floor colors and materials, ceiling lights and furniture exactly the same.")
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
SOLO_BACK_PROBLEM = ("Someone's back, head or shoulder is in the foreground. This is not an over-the-shoulder "
                     "shot: only this one person is in the frame, and nobody else appears close to the camera "
                     "or at the edges.")
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

    허리 위 샷이 전신으로 나오거나 다른 벽을 보는 것만 틀렸으면 그대로 쓴다. 전신은 거리두기에 어긋나지
    않고, 다른 벽도 같은 방이다. 지난 생성 275컷에서 다시 그린 이유의 대부분이 이 둘이었고, 허리 위 샷은
    다시 그려도 절반가량 또 전신으로 나왔다(2026-11). 대사 컷은 입 모양이 보여야 해서 허리 위 샷을 지킨다.
    """
    soft = [FACING_PROBLEM] + ([] if cut.dialogue else [MEDIUM_PROBLEM])
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
        if dest.exists() and not force:
            log.info("컷 %d 이미지 캐시 재사용", cut.index)
            return cut.index, dest
        loc = sb.location(cut.location)
        place_sheet = location_sheets.get(cut.location) if cut.location else None
        place = (PlaceCheck(sheet=place_sheet, description=loc.description, seats=seat_lines(sb, cut))
                 if loc and place_sheet else None)
        cast_check = CastCheck(people=[
            (p.appearance.split(".")[0].strip() if (p := sb.character(m.name)) else m.name) for m in sb.visible_cast(cut)
        ])
        # 혼자 보이는 대사 컷에는 앞 컷 그림을 참고로 주지 않는다. 두 사람 컷(같은 순간)이나 같은 벽 컷을 주면
        # 그 각도를 따라 그려, 상대 자리가 빈 의자로 보였다(2026-11 카페 일기 컷 3~5).
        solo = solo_listener_side(sb, cut, sb.visible_cast(cut)) is not None
        moment_image = None
        room = None if solo else room_shot(sb, cut)
        room_image = job.cut_image(room) if room else None
        prompt, references = cut_image_request(
            sb,
            cut,
            sheets=sheets,
            location_sheets=location_sheets,
            prompts=prompts,
            aspect_ratio=settings.aspect_ratio,
            moment_image=moment_image if moment_image and moment_image.exists() else None,
            room_image=room_image if room_image and room_image.exists() else None,
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

        await draw(prompt, "")
        # 그림 검사: 사람 수·성별·허리 위 크기·카메라 응시. 틀리면 무엇이 틀렸는지 알려주고 다시 그린다.
        checks = []
        for attempt in range(1, settings.image_check_retries + 2):
            if look is None:
                break
            try:
                seen = await look.look(image=dest, place=place, cast=cast_check)
            except Exception as exc:
                log.warning("컷 %d 그림 확인 실패 — 그대로 쓴다: %s", cut.index, exc)
                break
            problems = image_problems(sb, cut, seen)
            checks.append({"attempt": attempt, "problems": problems, "seen": seen.model_dump()})
            if not problems or attempt > settings.image_check_retries or not needs_redraw(cut, problems):
                break
            log.warning("컷 %d 그림 다시 그림(%d): %s", cut.index, attempt, problems)
            await draw(prompt + "\n\nTHE PREVIOUS ATTEMPT WAS WRONG. Fix this:\n- " + "\n- ".join(problems), f"_retry{attempt}")
        if checks:
            (job.cut_dir(cut.index) / "image_check.json").write_text(
                json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
        # 이미지를 새로 뽑았으면 기존 승인은 무효다.
        job.unapprove({cut.index})
        return cut.index, dest

    # 참고할 그림을 먼저 그린다: 같은 벽을 보는 첫 컷 → 그 방을 참고하는 컷.
    room_cuts = [c for c in targets if solo_listener_side(sb, c, sb.visible_cast(c)) is None
                 and room_shot(sb, c) is not None]
    first = [c for c in targets if c not in room_cuts]
    pairs = []
    for wave in (first, room_cuts):
        pairs += await asyncio.gather(*(one(c) for c in wave))
    job.record_stage(
        Stage.CUT_IMAGES,
        elapsed_s=time.perf_counter() - started,
        cuts=[i for i, _ in pairs],
    )
    return dict(pairs)


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
) -> tuple[str, list[Path]]:
    """컷 하나를 그릴 프롬프트와 레퍼런스(화면 속 인물 시트 → 장소 시트).

    컷 그림과 썸네일(가로 구도)이 같은 규칙으로 그려지도록 한곳에 둔다.
    """
    cast = sorted(sb.visible_cast(cut), key=lambda m: _POSITION_ORDER[m.position])
    people = [m for m in cast if m.name in sheets]
    place_sheet = location_sheets.get(cut.location)
    references = [sheets[m.name] for m in people] + ([place_sheet] if place_sheet else [])
    if room_image is not None:
        references.append(room_image)
    if moment_image is not None:
        references.append(moment_image)
    prompt = prompts.render(
        "cut_image.j2",
        people=people,
        cast=cast,
        solo_side=solo_listener_side(sb, cut, cast),
        location=sb.location(cut.location),
        has_location_sheet=place_sheet is not None,
        has_moment_image=moment_image is not None,
        has_room_image=room_image is not None,
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
