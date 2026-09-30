"""Reconstruction job-upload and job-read API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from ..models.job import JobCreatedResponse, JobRecord
from ..services.job_service import JobNotFoundError, JobService
from ..services.storage_service import UploadValidationError


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_service(request: Request) -> JobService:
    return JobService(request.app.state.settings)


def _normalized_job_id(job_id: str) -> str:
    try:
        return str(UUID(job_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found"},
        ) from exc


@router.post("", response_model=JobCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: Request,
    video: UploadFile = File(..., description="Required drone video (.mp4, .mov, .mkv, or .avi)."),
    gps_csv: UploadFile | None = File(default=None, description="Optional GPS CSV."),
    imu_csv: UploadFile | None = File(default=None, description="Optional IMU CSV."),
    metadata_json: UploadFile | None = File(default=None, description="Optional metadata JSON."),
) -> JobCreatedResponse:
    """Create a durable upload-only reconstruction job without running a pipeline."""

    try:
        job = await _job_service(request).create_job(video, gps_csv, imu_csv, metadata_json)
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_UPLOAD", "message": str(exc)},
        ) from exc

    return JobCreatedResponse(job_id=job.job_id, status=job.status, stage=job.stage)


@router.get("/{job_id}", response_model=JobRecord)
async def get_job(job_id: str, request: Request) -> JobRecord:
    """Read a persisted reconstruction job without exposing arbitrary filesystem paths."""

    try:
        return _job_service(request).get_job(_normalized_job_id(job_id))
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found"},
        ) from exc
