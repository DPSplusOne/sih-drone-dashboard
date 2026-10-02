"""Reconstruction job-upload and job-read API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from ..models.job import JobCreatedResponse, JobPreprocessResponse, JobRecord
from ..services.preprocessing_service import PreprocessingFailedError, PreprocessingInProgressError
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


@router.post("/{job_id}/preprocess", response_model=JobPreprocessResponse)
async def preprocess_job(job_id: str, request: Request) -> JobPreprocessResponse:
    """Run the verified Member 1 preprocessing stage for one uploaded video."""

    normalized_job_id = _normalized_job_id(job_id)
    try:
        job = await run_in_threadpool(_job_service(request).preprocess_job, normalized_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found"},
        ) from exc
    except PreprocessingInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PREPROCESSING_IN_PROGRESS", "message": str(exc)},
        ) from exc
    except PreprocessingFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PREPROCESSING_FAILED", "message": str(exc)},
        ) from exc

    if job.preprocessing is None:  # Defensive guard for the response contract.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "PREPROCESSING_SUMMARY_MISSING", "message": "Preprocessing summary was not saved"},
        )
    return JobPreprocessResponse(
        job_id=job.job_id,
        status=job.status,
        stage=job.stage,
        preprocessing=job.preprocessing,
    )
