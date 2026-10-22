"""대사 컷과 나머지 컷을 서로 다른 영상 provider로 보낸다(모델 비교·섞어 쓰기).

예: 대사 컷은 입 모양이 맞는 Veo, 나머지는 싼 모델. 핸들에 어느 쪽으로 보냈는지 적어 두고
조회·내려받기도 같은 쪽으로 보낸다.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ..models import VideoHandle, VideoResult, VideoStatus
from .base import VideoProvider


class RoutingVideoProvider:
    def __init__(self, default: VideoProvider, speaking: VideoProvider) -> None:
        self._routes = {"default": default, "speaking": speaking}

    def price_per_second(self, resolution: str) -> Decimal:
        return max(p.price_per_second(resolution) for p in self._routes.values())

    async def submit(self, *, speaking: bool = False, **kwargs) -> VideoHandle:
        route = "speaking" if speaking else "default"
        handle = await self._routes[route].submit(speaking=speaking, **kwargs)
        return handle.model_copy(update={"raw": {**handle.raw, "route": route}})

    def _for(self, handle: VideoHandle) -> VideoProvider:
        return self._routes[handle.raw.get("route", "default")]

    async def poll(self, handle: VideoHandle) -> VideoStatus:
        return await self._for(handle).poll(handle)

    async def fetch(self, handle: VideoHandle, dest: Path) -> VideoResult:
        return await self._for(handle).fetch(handle, dest)
