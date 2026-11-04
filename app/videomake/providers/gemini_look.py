"""LookProvider의 Gemini 구현 — 컷 그림을 보고 사람 수·성별·크기·카메라 응시(+ 장소)를 답한다.

그림 모델은 지시와 다르게 그리는 일이 있다(허리 위 샷인데 사람을 아주 작게, 50대 남자 인물을 여자로).
컷 그림 검사(stages/cut_images.py)가 이 답으로 다시 그릴지 정한다. 그림 한 장에 요청 한 번(약 1원).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from google import genai
from google.genai import types

from ..errors import ProviderError
from .base import CastCheck, PlaceCheck, TimedFrame, SeenFrame, SeenPerson, retry_on_rate_limit
from .gemini_listen import parse_heard

PROMPT = """Look at this image and answer in JSON only.
"people": one entry per clearly visible person, largest first and at most 8 entries (ignore tiny background
figures, posters and screens; a crowded room can have many people, list only the 8 largest), each with
  "gender": "m" or "f" ("" if you cannot tell),
  "height_ratio": the visible height of that person (from the top of the head to the lowest visible part)
                  divided by the image height, between 0 and 1,
  "legs_visible": true if that person's knees, lower legs or feet are visible in the image.
"looks_at_camera": true if any of the main, clearly visible people looks directly into the camera
  (small people far in the background of a crowded place do not count).
"split_frame": true if the image is divided into two or more separate pictures or panels (stacked, side by side,
  a collage or grid) instead of one continuous view. A window, mirror, door or screen inside one view is not a split.
"empty_seat": true if an empty chair, empty seat or empty place setting is clearly visible right across the table
  from, or right next to, the largest person, where a companion would sit.
"foreground_back": true if someone is seen from behind close to the camera, in the foreground or at an edge of
  the image (the back of a head, a shoulder or an arm), as in an over-the-shoulder shot.
"time_of_day": "day" if windows or doorways show daylight (a bright sky or sunlight coming in), "night" if they show
  a dark sky (black or deep dark blue), "" if no window or outdoor view is visible or you cannot tell.
{"people": [{"gender": "m", "height_ratio": 0.6, "legs_visible": false}], "looks_at_camera": false, "split_frame": false,
 "empty_seat": false, "foreground_back": false, "time_of_day": ""}"""

# 장소 확인: 두 번째 그림은 그 장소를 네 방향에서 본 시트다. 같은 곳인지, 어느 벽을 보는지 답한다.
PLACE_PROMPT = """
The second image is a reference sheet of the place where the first image should be set. The place:
{description}
Also answer:
"same_place": true if the first image is recognizably this same place (same wall and floor colors and
  materials, same kind of lights and furniture), false if it looks like a different place.
"facing": which side of the place the camera looks at in the first image, using the side names in the
  description: "entrance", "far", "left" or "right" ("" if you cannot tell).
{{"people": [...], "looks_at_camera": false, "same_place": true, "facing": "left"}}"""

# 자리 확인: 같은 사람이 컷마다 다른 테이블에 앉는 일이 있었다(2026-11 팔순 잔치 — 할아버지가 상석·입구 옆 테이블을 오감).
SEAT_PROMPT = """
Where these people should be in the first image (judge with the reference sheet of the place):
{seats}
"wrong_seat": the names of the people above who are clearly somewhere else in the first image (for example at
  a different table or near a different wall). Leave out anyone who is at the written spot, is not visible,
  or whose spot you cannot judge.
{{"wrong_seat": []}}"""

# 인물 확인(영상 프레임): 어깨너머 샷의 앞사람이 상대가 아니라 주인공 복제로 나오는 일이 있다.
CAST_PROMPT = """
The people who belong in this scene (nobody else should be there):
{people}
Also answer:
"duplicate_person": true if the same person (same face, hair and clothes) appears more than once in the
  image, for example once facing the camera and again as a blurred shoulder or back of the head in the foreground.
"unknown_person": true if a clearly visible person matches none of the people listed above
  (ignore tiny, far-away background figures and people seen only on posters or screens).
"cut_off_person": true if a person who matches none of the people listed above is cut off by the left or right
  edge of the image close to the camera (for example half a face, a blurred shoulder or arm at the very edge).
{{"people": [...], "looks_at_camera": false, "duplicate_person": false, "unknown_person": false,
  "cut_off_person": false}}"""

# 샷 사이 연결 확인: 영상 모델은 샷이 바뀌면 장면을 새로 꾸며 물건을 없애거나 손을 진열대 위로 옮긴다(관측).
CONTINUITY_PROMPT = """These frames are in time order from one short film clip. Each is labelled with its time
and shot number. What should happen in the clip: {scene}
Report only clear continuity errors that a viewer would notice:
- an object someone holds vanishes, appears from nowhere, or ends up in the other person's hand without
  the action above showing it being handed over;
- an action is repeated or reversed (something handed over and then taken back, or offered again);
- in a later shot people or their hands are somewhere else. Check this carefully: in each shot, what is
  under or behind the hands (open air, a counter, a table, a glass display case)? If a close-up of hands
  shows them resting on a surface that is not between the people in the earlier wider shots (for example
  they stood face to face on an open floor), that is an error;
- the place itself changes.
Ignore changes of camera angle, framing, blur and small natural movements. Hands or objects that are
simply outside the frame in one shot are not an error; only report what is visibly wrong.
First describe each shot in "shots": where the people stand, what each person holds, and what is directly
under or behind their hands. Then list the errors. Answer in JSON only, details in short Korean:
{{"shots": [{{"shot": 1, "people": "...", "holding": "...", "under_hands": "..."}}],
  "problems": [{{"at": "6.5s", "detail": "..."}}]}}  (problems is an empty list if there is no clear error)"""


class GeminiLookProvider:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    async def look(
        self, *, image: Path, place: PlaceCheck | None = None, cast: CastCheck | None = None
    ) -> SeenFrame:
        contents = [types.Part.from_bytes(data=image.read_bytes(), mime_type="image/png")]
        text = PROMPT
        if place is not None and place.sheet.exists():
            contents.append(types.Part.from_bytes(data=place.sheet.read_bytes(), mime_type="image/png"))
            text += PLACE_PROMPT.format(description=place.description)
            if place.seats:
                text += SEAT_PROMPT.format(seats="\n".join(f"- {s}" for s in place.seats))
        if cast is not None:
            text += CAST_PROMPT.format(people="\n".join(f"- {p}" for p in cast.people))
        contents.append(text)

        async def call():
            return await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
            )

        try:
            data = parse_heard((await retry_on_rate_limit(call, what="그림 확인", timeout=90)).text)
            people = [SeenPerson(gender=str(p.get("gender") or "").lower()[:1],
                                 height_ratio=float(p.get("height_ratio") or 0),
                                 legs_visible=bool(p.get("legs_visible")))
                      for p in data.get("people") or [] if isinstance(p, dict)]
        except Exception as exc:
            raise ProviderError(f"그림 확인 실패 ({self._model}): {exc}") from exc
        same = data.get("same_place")
        facing = str(data.get("facing") or "").lower().strip()
        return SeenFrame(
            people=people,
            looks_at_camera=bool(data.get("looks_at_camera")),
            split_frame=data.get("split_frame") is True,
            empty_seat=_flag(data.get("empty_seat")),
            foreground_back=_flag(data.get("foreground_back")),
            time_of_day=tod if (tod := str(data.get("time_of_day") or "").lower().strip()) in ("day", "night") else "",
            same_place=same if isinstance(same, bool) else None,
            facing=facing if facing in SIDES else "",
            duplicate_person=_flag(data.get("duplicate_person")),
            unknown_person=_flag(data.get("unknown_person")),
            cut_off_person=_flag(data.get("cut_off_person")),
            wrong_seat=[str(n) for n in data.get("wrong_seat") or [] if isinstance(n, str)],
        )

    async def continuity(self, *, frames: Sequence[TimedFrame], scene: str) -> list[str]:
        contents: list = []
        for f in frames:
            contents.append(f"[{f.time:.1f}s, shot {f.shot}]")
            contents.append(types.Part.from_bytes(data=f.image.read_bytes(), mime_type="image/png"))
        contents.append(CONTINUITY_PROMPT.format(scene=scene))

        async def call():
            return await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
            )

        try:
            data = parse_heard((await retry_on_rate_limit(call, what="샷 연결 확인", timeout=90)).text)
        except Exception as exc:
            raise ProviderError(f"샷 연결 확인 실패 ({self._model}): {exc}") from exc
        return [
            f"{p.get('at', '').strip()} {str(p.get('detail', '')).strip()}".strip()
            for p in data.get("problems") or [] if isinstance(p, dict) and p.get("detail")
        ]


def _flag(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


SIDES = ("entrance", "far", "left", "right")
