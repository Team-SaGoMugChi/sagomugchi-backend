"""VideoProvider의 Veo 3.1 구현.

확인된 제약 (google-genai SDK 소스 + 실제 호출 기준):
- reference_images와 first frame(image)은 배타적이다. SDK 원문:
  "If this field is provided ... The image, video, or last_frame field are not
  supported." → 우리는 first frame만 쓴다. 캐릭터 일관성은 이미지 단계에서 끝낸다.
- Vertex에서는 seed / generate_audio 를 쓸 수 있다. 다만 generate_audio=False로
  오디오 트랙을 아예 없애면 Compositor의 ffmpeg 매핑이 깨지므로 건드리지 않는다.
  나레이션 충돌은 지금처럼 Compositor에서 처리하고 발화는 negative_prompt로 억제한다.
- negative_prompt에 오디오 금지어를 과하게 넣으면 렌더가 통째로 실패한다.
  시각적 금지만 넣고 오디오는 motion 프롬프트로 유도한다.
- generate_videos는 long-running operation이므로 polling이 필수다.
- 동시 제출은 쉽게 429를 맞는다. 지수 백오프로 재시도한다.
- 영상 바이트는 operation 응답에 함께 온다. 완료 즉시 로컬에 저장한다.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import random
import time
from decimal import Decimal
from pathlib import Path

from google import genai
from google.genai import types

from ..cost import video_price_per_second
from ..errors import ProviderError
from ..models import VideoHandle, VideoResult, VideoStatus

log = logging.getLogger(__name__)


def _is_rate_limited(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


class VeoVideoProvider:
    def __init__(
        self, client: genai.Client, model: str, max_retries: int = 5
    ) -> None:
        self._client = client
        self._model = model
        self._max_retries = max_retries
        self._ops: dict[str, types.GenerateVideosOperation] = {}

    def price_per_second(self, resolution: str) -> Decimal:
        return video_price_per_second(self._model, resolution)

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
    ) -> VideoHandle:
        mime = mimetypes.guess_type(first_frame.name)[0] or "image/png"
        source = types.GenerateVideosSource(
            prompt=motion_prompt,
            image=types.Image(
                image_bytes=first_frame.read_bytes(), mime_type=mime
            ),
        )
        config = types.GenerateVideosConfig(
            number_of_videos=1,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            duration_seconds=duration_seconds,
            negative_prompt=negative_prompt,
            person_generation="allow_adult",
            # Vertex 전용. 대사 컷에서만 켠다. 나레이션 컷은 Compositor가
            # Veo 오디오를 어차피 버리므로 만들 이유가 없다.
            generate_audio=generate_audio,
        )

        op = None
        for attempt in range(1, self._max_retries + 1):
            try:
                op = await self._client.aio.models.generate_videos(
                    model=self._model, source=source, config=config
                )
                break
            except Exception as exc:
                if not _is_rate_limited(exc) or attempt == self._max_retries:
                    raise ProviderError(
                        f"컷 {cut_index} 영상 제출 실패: {exc}"
                    ) from exc
                delay = min(2**attempt, 60) + random.uniform(0, 2)
                log.warning(
                    "컷 %d rate limit. %.1fs 후 재시도 (%d/%d)",
                    cut_index,
                    delay,
                    attempt,
                    self._max_retries,
                )
                await asyncio.sleep(delay)

        assert op is not None
        name = op.name or f"cut-{cut_index}"
        self._ops[name] = op
        return VideoHandle(cut_index=cut_index, operation_name=name)

    def _operation(self, handle: VideoHandle) -> types.GenerateVideosOperation:
        """메모리에 없으면 저장된 이름으로 복원한다.

        프로세스가 죽어도 job 디렉터리의 핸들만 있으면 진행 중인 렌더를 회수할 수
        있다. 재제출하면 그만큼 다시 과금되므로 반드시 이어받아야 한다.
        """
        op = self._ops.get(handle.operation_name)
        if op is None:
            op = types.GenerateVideosOperation(name=handle.operation_name)
            self._ops[handle.operation_name] = op
        return op

    async def poll(self, handle: VideoHandle) -> VideoStatus:
        op = self._operation(handle)
        try:
            op = await self._client.aio.operations.get(op)
        except Exception as exc:
            raise ProviderError(f"operation 조회 실패: {exc}") from exc
        self._ops[handle.operation_name] = op

        if op.error:
            return VideoStatus(done=True, failed=True, error=str(op.error))
        return VideoStatus(done=bool(op.done))

    async def fetch(self, handle: VideoHandle, dest: Path) -> VideoResult:
        op = self._ops.get(handle.operation_name)
        if op is None or not op.done:
            raise ProviderError(f"컷 {handle.cut_index}이 아직 완료되지 않았다")

        response = op.response or op.result
        videos = getattr(response, "generated_videos", None) or []
        if not videos:
            filtered = getattr(response, "rai_media_filtered_reasons", None)
            raise ProviderError(
                f"컷 {handle.cut_index}: 생성된 영상이 없다. "
                f"안전 필터 사유: {filtered or 'unknown'}"
            )

        started = time.perf_counter()
        video = videos[0].video
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Vertex는 output_gcs_uri를 주지 않으면 video_bytes를 응답에 실어 보낸다.
            # files.download는 Developer API 전용이라 Vertex에서는 ValueError다.
            await asyncio.to_thread(video.save, str(dest))
        except Exception as exc:
            raise ProviderError(f"컷 {handle.cut_index} 다운로드 실패: {exc}") from exc

        return VideoResult(path=str(dest), elapsed_s=time.perf_counter() - started)
