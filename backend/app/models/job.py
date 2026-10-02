"""Schemas persisted for reconstruction-job ingestion."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class JobStage(str, Enum):
    UPLOADED = "UPLOADED"
    PREPROCESSING = "PREPROCESSING"
    PREPROCESSED = "PREPROCESSED"
    FAILED = "FAILED"


class JobInput(BaseModel):
    """Metadata about one server-persisted upload."""

    original_filename: str
    stored_filename: str
    size_bytes: int = Field(ge=0)
    content_type: str | None = None


class JobInputs(BaseModel):
    video: JobInput
    gps_csv: JobInput | None = None
    imu_csv: JobInput | None = None
    metadata_json: JobInput | None = None


class PreprocessingSettings(BaseModel):
    """The fixed, verified settings used for an SfM preprocessing run."""

    sample_fps: float = 2.0
    blur_threshold: float = 100.0
    difference_threshold: float = 12.0
    enable_stabilization: bool = False


class PreprocessingArtifacts(BaseModel):
    """Job-relative paths to preprocessing outputs safe to expose through the API."""

    frames_dir: str = "frames"
    extracted_frames_dir: str = "extracted"
    stabilized_frames_dir: str = "stabilized"
    keyframes_dir: str = "keyframes"
    video_metadata_path: str = "preprocessing/video_metadata.json"
    frame_metadata_path: str = "preprocessing/frame_metadata.csv"
    keyframes_manifest_path: str = "preprocessing/keyframes_manifest.csv"
    quality_report_path: str = "preprocessing/quality_report.json"


class PreprocessingSummary(BaseModel):
    """Durable result of the Member 1 preprocessing stage."""

    settings: PreprocessingSettings
    video_metadata: dict[str, Any]
    quality_report: dict[str, Any]
    artifacts: PreprocessingArtifacts


class JobRecord(BaseModel):
    """Durable job state stored as `job.json` during Phase 2."""

    job_id: str
    status: JobStatus = JobStatus.UPLOADED
    stage: JobStage = JobStage.UPLOADED
    progress: int = Field(default=0, ge=0, le=100)
    created_at: datetime
    updated_at: datetime
    inputs: JobInputs
    error: dict[str, str] | None = None
    preprocessing: PreprocessingSummary | None = None


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    stage: JobStage


class JobPreprocessResponse(BaseModel):
    """Response returned when a job's preprocessing stage completes."""

    job_id: str
    status: JobStatus
    stage: JobStage
    preprocessing: PreprocessingSummary
