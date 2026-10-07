"""Job 디렉터리 = 파이프라인의 상태 저장소.

각 단계 산출물을 파일로 남기고 재실행 시 캐시를 재사용한다. 실패한 컷만
다시 만들 수 있어야 하므로 컷 단위로 디렉터리를 분리한다.

OddO 이식 시: 이 클래스의 인터페이스를 유지한 채 S3/DB 구현으로 갈아끼운다.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .errors import ApprovalRequired
from .models import Stage, Storyboard


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JobStore:
    def __init__(self, root: Path, job_id: str) -> None:
        self.job_id = job_id
        self.dir = Path(root) / job_id
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "cuts").mkdir(exist_ok=True)
        (self.dir / "logs").mkdir(exist_ok=True)
        if not self.manifest_path.exists():
            self._write_manifest(
                {
                    "job_id": job_id,
                    "created_at": _now(),
                    "stages": {},
                    "approvals": {},
                    "costs": [],
                }
            )

    # --- 경로 ---------------------------------------------------------------
    @property
    def manifest_path(self) -> Path:
        return self.dir / "manifest.json"

    @property
    def input_path(self) -> Path:
        return self.dir / "input.json"

    @property
    def storyboard_path(self) -> Path:
        return self.dir / "storyboard.json"

    @property
    def character_sheet_path(self) -> Path:
        return self.dir / "character_sheet.png"

    def supporting_sheet(self, index: int) -> Path:
        """조연 캐릭터 시트(supporting 목록 순서, 1부터)."""
        return self.dir / "sheets" / f"character_{index:02d}.png"

    def location_sheet(self, index: int) -> Path:
        """장소 시트 — 같은 장소를 여러 방향에서 본 그림(locations 목록 순서, 1부터)."""
        return self.dir / "sheets" / f"location_{index:02d}.png"

    @property
    def review_path(self) -> Path:
        return self.dir / "review.html"

    @property
    def final_path(self) -> Path:
        return self.dir / "final.mp4"

    @property
    def thumbnail_path(self) -> Path:
        """대표 장면 가로 썸네일(앱 홈 카드용)."""
        return self.dir / "thumbnail.jpg"

    def cut_dir(self, index: int) -> Path:
        d = self.dir / "cuts" / f"{index:02d}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def cut_image(self, index: int) -> Path:
        return self.cut_dir(index) / "image.png"

    def cut_video(self, index: int) -> Path:
        return self.cut_dir(index) / "video.mp4"

    def cut_narration(self, index: int) -> Path:
        return self.cut_dir(index) / "narration.wav"

    def cut_handle(self, index: int) -> Path:
        return self.cut_dir(index) / "video_handle.json"

    # --- manifest -----------------------------------------------------------
    def manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _write_manifest(self, data: dict[str, Any]) -> None:
        self.manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def record_stage(
        self, stage: Stage, *, elapsed_s: float = 0.0, **extra: Any
    ) -> None:
        m = self.manifest()
        m["stages"][stage.value] = {
            "completed_at": _now(),
            "elapsed_s": round(elapsed_s, 2),
            **extra,
        }
        self._write_manifest(m)

    def record_cost(self, label: str, usd: Decimal) -> None:
        m = self.manifest()
        m["costs"].append({"at": _now(), "label": label, "usd": str(usd)})
        self._write_manifest(m)

    def spent_usd(self) -> Decimal:
        return sum(
            (Decimal(c["usd"]) for c in self.manifest()["costs"]), Decimal(0)
        )

    # --- 스토리보드 ----------------------------------------------------------
    def save_storyboard(self, sb: Storyboard) -> None:
        self.storyboard_path.write_text(
            sb.model_dump_json(indent=2), encoding="utf-8"
        )

    def load_storyboard(self) -> Storyboard:
        return Storyboard.model_validate_json(
            self.storyboard_path.read_text(encoding="utf-8")
        )

    # --- 승인 게이트 ---------------------------------------------------------
    def approve(self, indices: set[int]) -> None:
        m = self.manifest()
        for i in indices:
            m["approvals"][str(i)] = {"approved_at": _now()}
        self._write_manifest(m)

    def unapprove(self, indices: set[int]) -> None:
        m = self.manifest()
        for i in indices:
            m["approvals"].pop(str(i), None)
        self._write_manifest(m)

    def approved_cuts(self) -> set[int]:
        return {int(k) for k in self.manifest()["approvals"]}

    def assert_approved(self, indices: set[int]) -> None:
        """영상 렌더 진입점에서 호출한다. 승인 없이 Veo를 부르는 경로를 코드에서 없앤다."""
        missing = sorted(indices - self.approved_cuts())
        if missing:
            raise ApprovalRequired(
                f"컷 {missing}이 아직 승인되지 않았다. "
                "`videomake review` 로 이미지를 확인하고 `videomake approve` 후 렌더할 것. "
                "영상은 컷당 약 $0.80이다."
            )

    # --- 재생성 -------------------------------------------------------------
    def invalidate_cut(self, index: int, *, images: bool = False) -> None:
        """컷 산출물을 지워 다음 실행에서 다시 만들게 한다."""
        for p in (self.cut_video(index), self.cut_handle(index)):
            p.unlink(missing_ok=True)
        if images:
            self.cut_image(index).unlink(missing_ok=True)
            self.unapprove({index})

    def reset(self) -> None:
        shutil.rmtree(self.dir)
