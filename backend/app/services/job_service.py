"""Application service for creating and reading reconstruction jobs."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import UploadFile

from ..config import Settings
from ..models.job import JobInputs, JobRecord
from .preprocessing_service import PreprocessingService
from .storage_service import JobNotFoundError, StorageService, ValidatedUpload


logger = logging.getLogger("aerotrace")


class JobService:
    """Coordinates upload validation, disk persistence, and job metadata."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = StorageService(settings.jobs_dir, settings.upload_chunk_size)

    async def create_job(
        self,
        video: UploadFile,
        gps_csv: UploadFile | None = None,
        imu_csv: UploadFile | None = None,
        metadata_json: UploadFile | None = None,
    ) -> JobRecord:
        """Persist validated uploads and publish a durable initial job record."""

        submitted_uploads = (video, gps_csv, imu_csv, metadata_json)
        job_id: str | None = None
        try:
            uploads = (
                (video, self.storage.validate_upload(video, "video", self.settings.allowed_video_extensions, required=True)),
                (gps_csv, self.storage.validate_upload(gps_csv, "gps_csv", self.settings.allowed_gps_extensions)),
                (imu_csv, self.storage.validate_upload(imu_csv, "imu_csv", self.settings.allowed_imu_extensions)),
                (
                    metadata_json,
                    self.storage.validate_upload(
                        metadata_json, "metadata_json", self.settings.allowed_metadata_extensions
                    ),
                ),
            )
            job_id = str(uuid.uuid4())
            job_dir = self.storage.create_job_directory(job_id)
            input_dir = job_dir / "input"
            video_input = await self.storage.stream_upload(
                video, input_dir / f"video.{uploads[0][1].suffix.lstrip('.')}", uploads[0][1]
            )
            gps_input = await self._save_optional_upload(uploads[1], input_dir / "gps.csv")
            imu_input = await self._save_optional_upload(uploads[2], input_dir / "imu.csv")
            metadata_input = await self._save_optional_upload(uploads[3], input_dir / "metadata.json")

            timestamp = datetime.now(timezone.utc)
            job = JobRecord(
                job_id=job_id,
                created_at=timestamp,
                updated_at=timestamp,
                inputs=JobInputs(
                    video=video_input,
                    gps_csv=gps_input,
                    imu_csv=imu_input,
                    metadata_json=metadata_input,
                ),
            )
            self.storage.write_job_record(job_dir, job)
            logger.info(
                "job_uploaded",
                extra={
                    "event": "job_uploaded",
                    "job_id": job_id,
                    "input_count": sum(input_value is not None for input_value in job.inputs.model_dump().values()),
                },
            )
            return job
        except Exception:
            if job_id is not None:
                self.storage.delete_job_directory(job_id)
            logger.exception("job_upload_failed", extra={"event": "job_upload_failed", "job_id": job_id})
            raise
        finally:
            for upload in submitted_uploads:
                if upload is not None:
                    await upload.close()

    async def _save_optional_upload(
        self, upload_with_info: tuple[UploadFile | None, ValidatedUpload | None], target_path
    ):
        upload, upload_info = upload_with_info
        if upload is None or upload_info is None:
            return None
        return await self.storage.stream_upload(upload, target_path, upload_info)

    def get_job(self, job_id: str) -> JobRecord:
        """Return a persisted job after UUID normalization in the route layer."""

        return self.storage.load_job_record(job_id)

    def preprocess_job(self, job_id: str) -> JobRecord:
        """Run the Member 1 preprocessing stage for a persisted job."""

        return PreprocessingService(self.storage).preprocess_job(job_id)


__all__ = ["JobNotFoundError", "JobService"]
