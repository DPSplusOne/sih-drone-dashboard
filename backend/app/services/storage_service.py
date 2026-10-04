"""Safe, streaming filesystem operations for reconstruction-job uploads."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from ..models.job import JobInput, JobRecord


class UploadValidationError(ValueError):
    """Raised when a submitted upload does not meet the input contract."""


class JobNotFoundError(FileNotFoundError):
    """Raised when a requested persisted job does not exist."""


@dataclass(frozen=True)
class ValidatedUpload:
    field_name: str
    original_filename: str
    suffix: str
    content_type: str | None


def _safe_original_filename(filename: str | None) -> str:
    """Discard any client-supplied directory components before recording metadata."""

    if not filename:
        return ""
    return filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()


class StorageService:
    """Owns the job-directory layout and durable artifact writes."""

    def __init__(self, jobs_dir: Path, upload_chunk_size: int) -> None:
        self.jobs_dir = jobs_dir
        self.upload_chunk_size = upload_chunk_size

    def validate_upload(
        self, upload: UploadFile | None, field_name: str, allowed_extensions: frozenset[str], required: bool = False
    ) -> ValidatedUpload | None:
        if upload is None:
            if required:
                raise UploadValidationError(f"{field_name} is required")
            return None

        original_filename = _safe_original_filename(upload.filename)
        suffix = Path(original_filename).suffix.lower()
        if not original_filename or suffix not in allowed_extensions:
            allowed = ", ".join(sorted(allowed_extensions))
            raise UploadValidationError(f"{field_name} must use one of: {allowed}")

        return ValidatedUpload(
            field_name=field_name,
            original_filename=original_filename,
            suffix=suffix,
            content_type=upload.content_type,
        )

    def create_job_directory(self, job_id: str) -> Path:
        """Create the complete fixed layout for one UUID-validated job."""

        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        for directory_name in (
            "input",
            "frames",
            "extracted",
            "stabilized",
            "keyframes",
            "preprocessing",
            "reconstruction",
            "outputs",
            "logs",
        ):
            (job_dir / directory_name).mkdir()
        return job_dir

    def job_directory(self, job_id: str) -> Path:
        """Return the fixed directory for a job whose record has already been loaded."""

        return self.jobs_dir / job_id

    def delete_job_directory(self, job_id: str) -> None:
        """Remove a partially created UUID job directory after a failed upload."""

        job_dir = self.jobs_dir / job_id
        if job_dir.is_dir():
            shutil.rmtree(job_dir)

    async def stream_upload(
        self, upload: UploadFile, target_path: Path, upload_info: ValidatedUpload
    ) -> JobInput:
        """Stream one upload to disk without retaining the full file in memory."""

        bytes_written = 0
        try:
            with target_path.open("xb") as destination:
                while chunk := await upload.read(self.upload_chunk_size):
                    destination.write(chunk)
                    bytes_written += len(chunk)
                destination.flush()
                os.fsync(destination.fileno())
        except Exception:
            target_path.unlink(missing_ok=True)
            raise

        return JobInput(
            original_filename=upload_info.original_filename,
            stored_filename=target_path.name,
            size_bytes=bytes_written,
            content_type=upload_info.content_type,
        )

    def write_job_record(self, job_dir: Path, job: JobRecord) -> None:
        """Write `job.json` atomically in the job directory."""

        target_path = job_dir / "job.json"
        temporary_path = job_dir / f".{target_path.name}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary_path.open("x", encoding="utf-8") as destination:
                json.dump(job.model_dump(mode="json"), destination, indent=2)
                destination.write("\n")
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary_path, target_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def load_job_record(self, job_id: str) -> JobRecord:
        """Load and validate a persisted job record by UUID-normalized ID."""

        record_path = self.jobs_dir / job_id / "job.json"
        if not record_path.is_file():
            raise JobNotFoundError(job_id)
        with record_path.open(encoding="utf-8") as source:
            return JobRecord.model_validate(json.load(source))
