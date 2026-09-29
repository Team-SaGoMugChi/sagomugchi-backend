"""videomake 더미 provider로 영상 파이프라인 전체를 돌린다. API 비용 0.

ffmpeg가 실제로 동작하므로 합성된 final.mp4까지 검증된다.
"""

import asyncio
import shutil
import subprocess

import pytest

from app.videomake.config import Settings
from app.videomake.errors import ConfigError
from app.videomake.job import JobStore
from app.videomake.models import DiaryInput
from app.videomake.pipeline import Pipeline
from app.videomake.providers import fake
from app.videomake.providers.registry import build_providers

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 필요")

DIARY = DiaryInput(
    text="오늘 회의에서 의견을 말했는데 팀장님이 바로 다른 얘기로 넘어갔다.",
    emotion={"primary": "슬픔", "intensity": 0.6},
)


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(fake, "STEP_DELAY_SECONDS", 0)


def _settings(tmp_path, n_cuts: int) -> Settings:
    return Settings(
        dummy=True,
        jobs_dir=tmp_path / "jobs",
        n_cuts=n_cuts,
        cut_duration_seconds=4,
        poll_interval_seconds=0.0,
    )


def _duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


def test_dummy_mode_needs_no_gcp_project(tmp_path):
    settings = _settings(tmp_path, n_cuts=1)
    assert settings.google_cloud_project == ""
    providers = build_providers(settings)
    assert providers.client is None


@pytest.mark.parametrize("n_cuts", [1, 3])
def test_dummy_pipeline_produces_final_mp4(tmp_path, n_cuts):
    settings = _settings(tmp_path, n_cuts=n_cuts)
    pipe = Pipeline(
        providers=build_providers(settings),
        job=JobStore(settings.jobs_dir, "dummy-job"),
        settings=settings,
    )

    async def run():
        sb = await pipe.run_to_gate(DIARY)
        pipe.approve(sb)
        return await pipe.finish(sb)

    final = asyncio.run(run())

    assert final.exists()
    assert abs(_duration(final) - 4 * n_cuts) < 0.5


def test_default_is_dummy_mode(monkeypatch):
    """VIDEOMAKE_DUMMY를 안 적으면 연습 모드다. 줄이 빠져도 과금되지 않는다."""
    monkeypatch.delenv("VIDEOMAKE_DUMMY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.dummy is True
    assert build_providers(settings).client is None


def test_real_mode_only_when_explicitly_false(monkeypatch):
    """false를 명시해야 실제 provider를 조립한다(GCP 프로젝트가 없으면 여기서 멈춘다)."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ConfigError, match="GOOGLE_CLOUD_PROJECT"):
        build_providers(Settings(_env_file=None, dummy=False))
