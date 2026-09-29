"""Configuration and filesystem setup for the AeroTrace 3D API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


DEFAULT_CORS_ORIGINS = (
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _path_from_environment(name: str, default: Path, project_root: Path) -> Path:
    """Return an absolute path from an optional environment variable."""

    raw_value = os.getenv(name)
    path = Path(raw_value).expanduser() if raw_value else default
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _cors_origins_from_environment() -> tuple[str, ...]:
    raw_value = os.getenv("CORS_ORIGINS")
    if not raw_value:
        return DEFAULT_CORS_ORIGINS
    return tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    """Application settings derived from environment variables."""

    project_root: Path
    data_dir: Path
    output_dir: Path
    jobs_dir: Path
    cors_origins: tuple[str, ...]
    log_level: str

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    def ensure_directories(self) -> None:
        """Create runtime directories required by the first pipeline phase."""

        for directory in (self.data_dir, self.raw_dir, self.jobs_dir, self.output_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_environment(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
        data_dir = _path_from_environment("DATA_DIR", project_root / "data", project_root)
        return cls(
            project_root=project_root,
            data_dir=data_dir,
            output_dir=_path_from_environment("OUTPUT_DIR", project_root / "outputs", project_root),
            jobs_dir=_path_from_environment("JOBS_DIR", data_dir / "jobs", project_root),
            cors_origins=_cors_origins_from_environment(),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings.from_environment()
