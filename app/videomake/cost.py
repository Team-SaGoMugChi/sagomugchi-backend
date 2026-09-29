"""비용 추정과 상한 가드.

원칙: 검수와 반복은 이미지 단계에서 끝낸다. 영상 렌더는 확정된 이미지에만 실행한다.
숫자로 보면 자명하다 — 컷 이미지 1장은 약 $0.045, 영상 1컷은 $0.80이다.
이미지를 17번 다시 뽑아도 영상 1컷보다 싸다.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from .errors import BudgetExceeded
from .models import CostEstimate, CostItem

# 2026-09 Gemini API 공개 단가. 변동이 잦으므로 여기 한 곳에서만 관리한다.
VIDEO_PRICE_PER_SECOND: dict[str, dict[str, Decimal]] = {
    "veo-3.1-fast": {"720p": Decimal("0.10"), "1080p": Decimal("0.12")},
    "veo-3.1-lite": {"720p": Decimal("0.05"), "1080p": Decimal("0.08")},
    "veo-3.1": {"720p": Decimal("0.40"), "1080p": Decimal("0.40")},
}

IMAGE_PRICE_PER_IMAGE: dict[str, dict[str, Decimal]] = {
    "gemini-3.1-flash-lite-image": {"1K": Decimal("0.0336"), "2K": Decimal("0.0336")},
    "gemini-3.1-flash-image": {"1K": Decimal("0.045"), "2K": Decimal("0.151")},
    "gemini-3-pro-image": {"1K": Decimal("0.134"), "2K": Decimal("0.24")},
    "gemini-2.5-flash-image": {"1K": Decimal("0.039"), "2K": Decimal("0.039")},
}

# 나레이션/스토리보드는 영상 대비 무시할 수준이지만 총액에는 넣는다.
TTS_PRICE_PER_CUT = Decimal("0.002")
LLM_PRICE_PER_STORYBOARD = Decimal("0.01")


def _lookup(table: dict[str, dict[str, Decimal]], model: str, key: str) -> Decimal:
    """모델 문자열의 접두사로 단가를 찾는다. 긴 접두사를 우선한다."""
    for prefix in sorted(table, key=len, reverse=True):
        if model.startswith(prefix):
            tier = table[prefix]
            if key in tier:
                return tier[key]
            return next(iter(tier.values()))
    raise KeyError(f"'{model}'의 단가를 모른다. cost.py의 단가표에 추가할 것.")


def video_price_per_second(model: str, resolution: str) -> Decimal:
    return _lookup(VIDEO_PRICE_PER_SECOND, model, resolution)


def image_price_per_image(model: str, image_size: str) -> Decimal:
    return _lookup(IMAGE_PRICE_PER_IMAGE, model, image_size)


def estimate_images(model: str, image_size: str, n_images: int) -> CostEstimate:
    unit = image_price_per_image(model, image_size)
    return CostEstimate(
        items=[
            CostItem(
                label=f"이미지 ({model}, {image_size})",
                quantity=Decimal(n_images),
                unit="장",
                unit_price_usd=unit,
                subtotal_usd=unit * n_images,
            )
        ]
    )


def estimate_videos(
    model: str, resolution: str, cut_seconds: list[int]
) -> CostEstimate:
    unit = video_price_per_second(model, resolution)
    total_s = Decimal(sum(cut_seconds))
    return CostEstimate(
        items=[
            CostItem(
                label=f"영상 ({model}, {resolution}, {len(cut_seconds)}컷)",
                quantity=total_s,
                unit="초",
                unit_price_usd=unit,
                subtotal_usd=unit * total_s,
            )
        ]
    )


def estimate_full_job(
    *,
    image_model: str,
    image_size: str,
    video_model: str,
    resolution: str,
    cut_seconds: list[int],
) -> CostEstimate:
    """캐릭터 시트 1장 + 컷 이미지 N장 + 영상 N컷 + 나레이션 N개 + 스토리보드."""
    n = len(cut_seconds)
    est = CostEstimate(items=[])
    est.items += estimate_images(image_model, image_size, n + 1).items
    est.items += estimate_videos(video_model, resolution, cut_seconds).items
    est.items.append(
        CostItem(
            label="나레이션 TTS",
            quantity=Decimal(n),
            unit="컷",
            unit_price_usd=TTS_PRICE_PER_CUT,
            subtotal_usd=TTS_PRICE_PER_CUT * n,
        )
    )
    est.items.append(
        CostItem(
            label="스토리보드 LLM",
            quantity=Decimal(1),
            unit="회",
            unit_price_usd=LLM_PRICE_PER_STORYBOARD,
            subtotal_usd=LLM_PRICE_PER_STORYBOARD,
        )
    )
    return est


def enforce_budget(
    estimate: CostEstimate,
    limit_usd: Decimal,
    *,
    confirm: Callable[[CostEstimate, Decimal], bool] | None = None,
) -> None:
    """상한 초과 시 명시적 확인 없이는 진행을 막는다."""
    if estimate.total_usd <= limit_usd:
        return
    if confirm is not None and confirm(estimate, limit_usd):
        return
    raise BudgetExceeded(
        f"예상 비용 ${estimate.total_usd:.2f}가 상한 ${limit_usd:.2f}를 넘는다. "
        "VIDEOMAKE_MAX_COST_USD를 올리거나 --yes로 명시적으로 승인할 것."
    )
