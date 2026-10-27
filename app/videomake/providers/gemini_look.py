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
"people": one entry per clearly visible person (ignore tiny background figures, posters and screens), each with
  "gender": "m" or "f" ("" if you cannot tell),
  "height_ratio": the visible height of that person (from the top of the head to the lowest visible part)
                  divided by the image height, between 0 and 1,
  "legs_visible": true if that person's knees, lower legs or feet are visible in the image.
"looks_at_camera": true if any person looks directly into the camera.
{"people": [{"gender": "m", "height_ratio": 0.6, "legs_visible": false}], "looks_at_camera": false}"""

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

# 인물 확인(영상 프레임): 어깨너머 샷의 앞사람이 상대가 아니라 주인공 복제로 나오는 일이 있다.
CAST_PROMPT = """
The people who belong in this scene (nobody else should be there):
{people}
Also answer:
"duplicate_person": true if the same person (same face, hair and clothes) appears more than once in the
  image, for example once facing the camera and again as a blurred shoulder or back of the head in the foreground.
"unknown_person": true if a clearly visible person matches none of the people listed above
  (ignore tiny, far-away background figures and people seen only on posters or screens).
{{"people": [...], "looks_at_camera": false, "duplicate_person": false, "unknown_person": false}}"""

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
            data = parse_heard((await retry_on_rate_limit(call, what="그림 확인")).text)
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
            same_place=same if isinstance(same, bool) else None,
            facing=facing if facing in SIDES else "",
            duplicate_person=_flag(data.get("duplicate_person")),
            unknown_person=_flag(data.get("unknown_person")),
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
            data = parse_heard((await retry_on_rate_limit(call, what="샷 연결 확인")).text)
        except Exception as exc:
            raise ProviderError(f"샷 연결 확인 실패 ({self._model}): {exc}") from exc
        return [
            f"{p.get('at', '').strip()} {str(p.get('detail', '')).strip()}".strip()
            for p in data.get("problems") or [] if isinstance(p, dict) and p.get("detail")
        ]


def _flag(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


SIDES = ("entrance", "far", "left", "right")
