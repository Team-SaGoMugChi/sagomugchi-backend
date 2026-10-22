"""VideoProvider의 evolink.ai 구현 — 여러 회사의 영상 모델을 한 API로 부른다(모델 비교용).

요청은 모두 `POST /v1/videos/generations` → `GET /v1/tasks/{id}`로 같지만 모델마다 칸 이름과
허용 값이 다르다(첫 프레임 `image_urls` vs `image_start`, 길이 6·10초만 등). 그 차이는 MODELS 표에
모아 둔다. 그림은 URL로만 받으므로 컷 그림을 image_host로 올려 서명된 주소를 넘긴다.

- 길이: 모델이 컷 길이를 못 만들면 그보다 긴 가장 짧은 값으로 만들고, 합성(compose)이 컷 길이로 자른다.
- 금지어 칸이 없는 모델은 금지어를 프롬프트 끝에 "Avoid:"로 붙인다.
- 소리: 소리를 만들 수 있는 모델만 generate_audio를 따른다. 못 만드는 모델은 대사 컷 입이 움직이지 않는다.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from ..errors import ProviderError
from ..models import VideoHandle, VideoResult, VideoStatus
from .image_host import FirebaseImageHost

log = logging.getLogger(__name__)

CREDIT_USD = Decimal("0.0152")  # 660크레딧 = $10 충전 기준


@dataclass(frozen=True)
class ModelSpec:
    image_field: str  # "image_urls"(배열) 또는 "image_start"(문자열)
    durations: tuple[int, ...]
    quality: str | None = None
    audio_field: str | None = None  # "generate_audio"(bool) 또는 "sound"("on"/"off")
    aspect_field: bool = False
    negative_field: bool = False
    extra: dict[str, Any] = field(default_factory=dict)
    # 공개 가격표의 대략값(가장 낮은 옵션). 실제 차감은 작업 결과에서 기록한다.
    credits_per_second: Decimal = Decimal(0)


_RANGE = lambda a, b: tuple(range(a, b + 1))  # noqa: E731

MODELS: dict[str, ModelSpec] = {
    "seedance-2.0-mini-image-to-video": ModelSpec(
        "image_urls", _RANGE(4, 15), quality="720p", audio_field="generate_audio",
        aspect_field=True, extra={"content_filter": False}, credits_per_second=Decimal("0.82"),
    ),
    "seedance-2.0-fast-image-to-video": ModelSpec(
        "image_urls", _RANGE(4, 15), quality="720p", audio_field="generate_audio",
        aspect_field=True, extra={"content_filter": False}, credits_per_second=Decimal("2.31"),
    ),
    "MiniMax-Hailuo-2.3-Fast": ModelSpec(
        "image_urls", (6, 10), quality="768p", credits_per_second=Decimal("2.0"),
    ),
    "MiniMax-Hailuo-02": ModelSpec(
        "image_urls", (6, 10), quality="768p", credits_per_second=Decimal("0.9"),
    ),
    "minimax-h3-max-turbo-image-to-video": ModelSpec(
        "image_start", _RANGE(5, 15), quality="768p", credits_per_second=Decimal("1.63"),
    ),
    "wan2.5-image-to-video": ModelSpec(
        "image_urls", (5, 10), quality="720p", extra={"prompt_extend": False},
        credits_per_second=Decimal("2.59"),
    ),
    "grok-imagine-image-to-video-beta": ModelSpec(
        "image_urls", _RANGE(6, 30), quality="720p", extra={"mode": "normal"},
        credits_per_second=Decimal("1.36"),
    ),
    "kling-v3-image-to-video": ModelSpec(
        "image_start", _RANGE(3, 15), quality="720p", audio_field="sound",
        negative_field=True, credits_per_second=Decimal("5.44"),
    ),
}


def request_duration(spec: ModelSpec, seconds: int) -> int:
    """컷 길이 이상인 가장 짧은 허용 길이. 없으면 가장 긴 값."""
    longer = [d for d in spec.durations if d >= seconds]
    return min(longer) if longer else max(spec.durations)


def build_body(
    model: str,
    spec: ModelSpec,
    *,
    prompt: str,
    image_url: str,
    negative_prompt: str,
    aspect_ratio: str,
    duration_seconds: int,
    generate_audio: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "duration": request_duration(spec, duration_seconds)}
    if spec.negative_field:
        body["negative_prompt"] = negative_prompt
    elif negative_prompt:
        prompt = f"{prompt}\n\nAvoid: {negative_prompt}"
    body["prompt"] = prompt
    body[spec.image_field] = [image_url] if spec.image_field == "image_urls" else image_url
    if spec.quality:
        body["quality"] = spec.quality
    if spec.aspect_field:
        body["aspect_ratio"] = aspect_ratio
    if spec.audio_field == "generate_audio":
        body["generate_audio"] = generate_audio
    elif spec.audio_field == "sound":
        body["sound"] = "on" if generate_audio else "off"
    body.update(spec.extra)
    return body


class EvolinkVideoProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        image_host: FirebaseImageHost,
        base_url: str = "https://api.evolink.ai",
        job_key: str = "job",
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
        quality: str | None = None,
    ) -> None:
        if model not in MODELS:
            raise ProviderError(f"evolink 모델 {model!r}의 요청 형식을 모른다. MODELS에 추가할 것.")
        self._model = model
        self._spec = MODELS[model]
        if quality:
            from dataclasses import replace

            self._spec = replace(self._spec, quality=quality)
        self._host = image_host
        self._job_key = job_key
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self._results: dict[str, dict[str, Any]] = {}

    def price_per_second(self, resolution: str) -> Decimal:
        return self._spec.credits_per_second * CREDIT_USD

    async def submit(
        self,
        *,
        cut_index: int,
        motion_prompt: str,
        first_frame: Path,
        negative_prompt: str,
        aspect_ratio: str,
        resolution: str,
        duration_seconds: int,
        generate_audio: bool = False,
        speaking: bool = False,
    ) -> VideoHandle:
        # 작업마다 다른 이름으로 올린다(동시에 도는 작업끼리 덮어쓰지 않게).
        key = f"{self._job_key}-{uuid.uuid4().hex[:10]}/cut{cut_index:02d}{first_frame.suffix}"
        url = await self._host.url_for(first_frame, key)
        body = build_body(
            self._model, self._spec,
            prompt=motion_prompt, image_url=url, negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio, duration_seconds=duration_seconds,
            generate_audio=generate_audio,
        )
        resp = await self._client.post("/v1/videos/generations", json=body)
        data = _json(resp)
        if resp.status_code >= 400 or "id" not in data:
            raise ProviderError(f"컷 {cut_index} evolink 제출 실패 ({resp.status_code}): {data}")
        log.info(
            "컷 %d evolink 제출 %s (%ss 요청) 예약 크레딧=%s",
            cut_index, self._model, body["duration"], _credits(data),
        )
        return VideoHandle(
            cut_index=cut_index,
            operation_name=data["id"],
            raw={"provider": "evolink", "model": self._model, "submit": _summary(data),
                 "requested_seconds": body["duration"]},
        )

    async def poll(self, handle: VideoHandle) -> VideoStatus:
        resp = await self._client.get(f"/v1/tasks/{handle.operation_name}")
        data = _json(resp)
        if resp.status_code >= 400:
            raise ProviderError(f"evolink 작업 조회 실패 ({resp.status_code}): {data}")
        status = data.get("status")
        if status == "failed":
            err = data.get("error") or {}
            return VideoStatus(done=True, failed=True, error=f"{err.get('code')}: {err.get('message')}", raw=_summary(data))
        if status == "completed":
            self._results[handle.operation_name] = data
            return VideoStatus(done=True, raw=_summary(data))
        return VideoStatus(done=False, raw=_summary(data))

    async def fetch(self, handle: VideoHandle, dest: Path) -> VideoResult:
        data = self._results.get(handle.operation_name)
        if data is None:
            resp = await self._client.get(f"/v1/tasks/{handle.operation_name}")
            data = _json(resp)
        url = _video_url(data)
        if not url:
            raise ProviderError(f"컷 {handle.cut_index}: evolink 결과에 영상 주소가 없다: {_summary(data)}")
        started = time.perf_counter()
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as dl:
            r = await dl.get(url)
            if r.status_code >= 400:
                raise ProviderError(f"컷 {handle.cut_index} 다운로드 실패 ({r.status_code})")
            dest.write_bytes(r.content)
        credits = _credits(data)
        log.info("컷 %d evolink 완료 — 차감 크레딧=%s", handle.cut_index, credits)
        cost = Decimal(str(credits)) * CREDIT_USD if credits is not None else Decimal(0)
        return VideoResult(path=str(dest), cost_usd=cost, elapsed_s=time.perf_counter() - started)


def _json(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        return {"text": resp.text[:500]}
    return data if isinstance(data, dict) else {"data": data}


def _video_url(data: dict[str, Any]) -> str | None:
    results = data.get("results") or []
    if results and isinstance(results[0], str):
        return results[0]
    for item in data.get("result_data") or []:
        if isinstance(item, dict) and item.get("url"):
            return item["url"]
    return None


def _credits(data: dict[str, Any]) -> float | None:
    usage = data.get("usage") or {}
    for key in ("credits_used", "credits", "credits_reserved", "consumed_credits"):
        for src in (usage, data, data.get("task_info") or {}):
            if isinstance(src, dict) and src.get(key) is not None:
                try:
                    return float(src[key])
                except (TypeError, ValueError):
                    pass
    return None


def _summary(data: dict[str, Any]) -> dict[str, Any]:
    keep = ("id", "status", "progress", "usage", "error", "task_info", "credits_reserved", "results")
    return {k: data[k] for k in keep if k in data}
