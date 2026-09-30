from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.app.config import (
    DEFAULT_GPS_EXTENSIONS,
    DEFAULT_IMU_EXTENSIONS,
    DEFAULT_METADATA_EXTENSIONS,
    DEFAULT_VIDEO_EXTENSIONS,
    Settings,
)
from backend.app.main import create_app


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "outputs",
        jobs_dir=tmp_path / "data" / "jobs",
        cors_origins=("http://127.0.0.1:5500",),
        log_level="INFO",
        upload_chunk_size=8,
        allowed_video_extensions=DEFAULT_VIDEO_EXTENSIONS,
        allowed_gps_extensions=DEFAULT_GPS_EXTENSIONS,
        allowed_imu_extensions=DEFAULT_IMU_EXTENSIONS,
        allowed_metadata_extensions=DEFAULT_METADATA_EXTENSIONS,
    )


@pytest.fixture
def test_app(test_settings):
    return create_app(test_settings)


def request(test_app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=test_app)
        async with test_app.router.lifespan_context(test_app):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, path, **kwargs)

    return asyncio.run(send_request())
