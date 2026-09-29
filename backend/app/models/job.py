"""Schemas persisted for reconstruction-job ingestion."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    UPLOADED = "uploaded"


class JobStage(str, Enum):
    UPLOADED = "UPLOADED"


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


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    stage: JobStage
