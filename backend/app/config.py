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

DEFAULT_UPLOAD_CHUNK_SIZE = 1024 * 1024
DEFAULT_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".avi"})
DEFAULT_GPS_EXTENSIONS = frozenset({".csv"})
DEFAULT_IMU_EXTENSIONS = frozenset({".csv"})
DEFAULT_METADATA_EXTENSIONS = frozenset({".json"})
DEFAULT_PREPROCESSING_DECODER = "ffmpeg"
DEFAULT_SAMPLE_FPS = 2.0
DEFAULT_BLUR_THRESHOLD = 100.0
DEFAULT_DIFFERENCE_THRESHOLD = 12.0
DEFAULT_PREPROCESSING_WORKERS = 1
DEFAULT_CHUNK_SECONDS = 30.0
DEFAULT_CHUNK_OVERLAP_SECONDS = 1.0


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


def _upload_chunk_size_from_environment() -> int:
    raw_value = os.getenv("UPLOAD_CHUNK_SIZE")
    if not raw_value:
        return DEFAULT_UPLOAD_CHUNK_SIZE
    try:
        chunk_size = int(raw_value)
    except ValueError as exc:
        raise ValueError("UPLOAD_CHUNK_SIZE must be a positive integer") from exc
    if chunk_size <= 0:
        raise ValueError("UPLOAD_CHUNK_SIZE must be a positive integer")
    return chunk_size


def _extensions_from_environment(name: str, default: frozenset[str]) -> frozenset[str]:
    raw_value = os.getenv(name)
    if not raw_value:
        return default

    extensions = frozenset(
        extension if extension.startswith(".") else f".{extension}"
        for extension in (value.strip().lower() for value in raw_value.split(","))
        if extension and extension != "."
    )
    if not extensions:
        raise ValueError(f"{name} must contain at least one extension")
    return extensions


def _boolean_from_environment(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _positive_int_from_environment(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_float_from_environment(name: str, default: float, *, allow_zero: bool = False) -> float:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a {'non-negative' if allow_zero else 'positive'} number") from exc
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be a {'non-negative' if allow_zero else 'positive'} number")
    return value


def _decoder_from_environment() -> str:
    decoder = os.getenv("PREPROCESSING_DECODER", DEFAULT_PREPROCESSING_DECODER).strip().lower()
    if decoder not in {"ffmpeg", "opencv"}:
        raise ValueError("PREPROCESSING_DECODER must be either 'ffmpeg' or 'opencv'")
    return decoder


@dataclass(frozen=True)
class Settings:
    """Application settings derived from environment variables."""

    project_root: Path
    data_dir: Path
    output_dir: Path
    jobs_dir: Path
    cors_origins: tuple[str, ...]
    log_level: str
    upload_chunk_size: int
    allowed_video_extensions: frozenset[str]
    allowed_gps_extensions: frozenset[str]
    allowed_imu_extensions: frozenset[str]
    allowed_metadata_extensions: frozenset[str]
    ffmpeg_executable: str = "ffmpeg"
    ffprobe_executable: str = "ffprobe"
    preprocessing_decoder: str = DEFAULT_PREPROCESSING_DECODER
    sample_fps: float = DEFAULT_SAMPLE_FPS
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD
    difference_threshold: float = DEFAULT_DIFFERENCE_THRESHOLD
    enable_stabilization: bool = False
    parallel_extraction: bool = False
    preprocessing_workers: int = DEFAULT_PREPROCESSING_WORKERS
    chunk_seconds: float = DEFAULT_CHUNK_SECONDS
    chunk_overlap_seconds: float = DEFAULT_CHUNK_OVERLAP_SECONDS

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
            upload_chunk_size=_upload_chunk_size_from_environment(),
            allowed_video_extensions=_extensions_from_environment(
                "ALLOWED_VIDEO_EXTENSIONS", DEFAULT_VIDEO_EXTENSIONS
            ),
            allowed_gps_extensions=_extensions_from_environment("ALLOWED_GPS_EXTENSIONS", DEFAULT_GPS_EXTENSIONS),
            allowed_imu_extensions=_extensions_from_environment("ALLOWED_IMU_EXTENSIONS", DEFAULT_IMU_EXTENSIONS),
            allowed_metadata_extensions=_extensions_from_environment(
                "ALLOWED_METADATA_EXTENSIONS", DEFAULT_METADATA_EXTENSIONS
            ),
            ffmpeg_executable=os.getenv("FFMPEG_EXECUTABLE", "ffmpeg"),
            ffprobe_executable=os.getenv("FFPROBE_EXECUTABLE", "ffprobe"),
            preprocessing_decoder=_decoder_from_environment(),
            sample_fps=_positive_float_from_environment("SAMPLE_FPS", DEFAULT_SAMPLE_FPS),
            blur_threshold=_positive_float_from_environment(
                "BLUR_THRESHOLD", DEFAULT_BLUR_THRESHOLD, allow_zero=True
            ),
            difference_threshold=_positive_float_from_environment(
                "DIFFERENCE_THRESHOLD", DEFAULT_DIFFERENCE_THRESHOLD, allow_zero=True
            ),
            enable_stabilization=_boolean_from_environment("ENABLE_STABILIZATION", False),
            parallel_extraction=_boolean_from_environment("PARALLEL_EXTRACTION", False),
            preprocessing_workers=_positive_int_from_environment("WORKERS", DEFAULT_PREPROCESSING_WORKERS),
            chunk_seconds=_positive_float_from_environment("CHUNK_SECONDS", DEFAULT_CHUNK_SECONDS),
            chunk_overlap_seconds=_positive_float_from_environment(
                "CHUNK_OVERLAP_SECONDS", DEFAULT_CHUNK_OVERLAP_SECONDS, allow_zero=True
            ),
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings.from_environment()
