"""Job-level adapter for the verified Member 1 preprocessing module.

The computer-vision implementation intentionally stays in ``member1_source``.
This service only supplies the fixed project settings, manages job state, and
places its artifacts in the durable job-directory layout.
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..models.job import (
    JobRecord,
    JobStage,
    JobStatus,
    PreprocessingArtifacts,
    PreprocessingSettings,
    PreprocessingSummary,
)
from .storage_service import JobNotFoundError, StorageService


logger = logging.getLogger("aerotrace")

SAMPLE_FPS = 2.0
BLUR_THRESHOLD = 100.0
DIFFERENCE_THRESHOLD = 12.0
ENABLE_STABILIZATION = False

REPORT_FILENAMES = (
    "video_metadata.json",
    "frame_metadata.csv",
    "keyframes_manifest.csv",
    "quality_report.json",
)


class PreprocessingFailedError(RuntimeError):
    """Raised after a preprocessing failure was recorded on the job."""


class PreprocessingInProgressError(RuntimeError):
    """Raised when a second request attempts to process an active job."""


def _run_preprocessing(**kwargs: Any) -> dict[str, Any]:
    """Load OpenCV-dependent code only when preprocessing is requested."""

    from member1_source.preprocessing import run_preprocessing

    return run_preprocessing(**kwargs)


class PreprocessingService:
    """Runs Member 1 preprocessing and publishes its artifacts for one job."""

    def __init__(self, storage: StorageService) -> None:
        self.storage = storage

    def preprocess_job(self, job_id: str) -> JobRecord:
        """Run preprocessing with fixed verified settings and persist its result."""

        job = self.storage.load_job_record(job_id)
        if job.status is JobStatus.PROCESSING:
            raise PreprocessingInProgressError(f"Job {job_id} is already preprocessing")

        job_dir = self.storage.job_directory(job_id)
        staging_dir = job_dir / f".preprocessing-{uuid.uuid4().hex}"
        self._set_processing(job, job_dir)

        try:
            video_path = job_dir / "input" / job.inputs.video.stored_filename
            if not video_path.is_file():
                raise FileNotFoundError(f"Uploaded video is missing: {job.inputs.video.stored_filename}")

            result = _run_preprocessing(
                video_path=video_path,
                output_root=staging_dir,
                sample_fps=SAMPLE_FPS,
                blur_threshold=BLUR_THRESHOLD,
                difference_threshold=DIFFERENCE_THRESHOLD,
                enable_stabilization=ENABLE_STABILIZATION,
            )
            summary = self._publish_outputs(staging_dir, job_dir, result)

            job.status = JobStatus.READY
            job.stage = JobStage.PREPROCESSED
            job.progress = 100
            job.error = None
            job.preprocessing = summary
            job.updated_at = datetime.now(timezone.utc)
            self.storage.write_job_record(job_dir, job)
            logger.info("job_preprocessed", extra={"event": "job_preprocessed", "job_id": job_id})
            return job
        except Exception as exc:
            diagnostic = self._diagnostic(exc)
            job.status = JobStatus.FAILED
            job.stage = JobStage.FAILED
            job.error = diagnostic
            job.updated_at = datetime.now(timezone.utc)
            self.storage.write_job_record(job_dir, job)
            logger.exception(
                "job_preprocessing_failed",
                extra={"event": "job_preprocessing_failed", "job_id": job_id, "error_code": diagnostic["code"]},
            )
            raise PreprocessingFailedError(diagnostic["message"]) from exc
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)

    def _set_processing(self, job: JobRecord, job_dir: Path) -> None:
        job.status = JobStatus.PROCESSING
        job.stage = JobStage.PREPROCESSING
        job.progress = 0
        job.error = None
        job.updated_at = datetime.now(timezone.utc)
        self.storage.write_job_record(job_dir, job)

    def _publish_outputs(
        self, staging_dir: Path, job_dir: Path, result: dict[str, Any]
    ) -> PreprocessingSummary:
        """Replace only the preprocessing artifacts after a complete successful run."""

        self._validate_staging_outputs(staging_dir)
        video_metadata = self._result_section(result, "video_metadata", staging_dir / "video_metadata.json")
        quality_report = self._result_section(result, "quality_report", staging_dir / "quality_report.json")

        published_metadata_dir = staging_dir / "published_preprocessing"
        published_metadata_dir.mkdir()
        for filename in REPORT_FILENAMES:
            shutil.move(str(staging_dir / filename), str(published_metadata_dir / filename))
        shutil.move(str(staging_dir / "blurry_frames"), str(published_metadata_dir / "blurry_frames"))
        shutil.move(
            str(staging_dir / "lowest_blur_scores"), str(published_metadata_dir / "lowest_blur_scores")
        )

        stabilized_source = staging_dir / "stabilized_frames"
        stabilized_source.mkdir(exist_ok=True)
        directory_mappings = (
            (staging_dir / "good_frames", job_dir / "frames"),
            (staging_dir / "extracted_frames", job_dir / "extracted"),
            (stabilized_source, job_dir / "stabilized"),
            (staging_dir / "keyframes", job_dir / "keyframes"),
            (published_metadata_dir, job_dir / "preprocessing"),
        )
        for source, destination in directory_mappings:
            self._replace_directory(source, destination)

        return PreprocessingSummary(
            settings=PreprocessingSettings(
                sample_fps=SAMPLE_FPS,
                blur_threshold=BLUR_THRESHOLD,
                difference_threshold=DIFFERENCE_THRESHOLD,
                enable_stabilization=ENABLE_STABILIZATION,
            ),
            video_metadata=video_metadata,
            quality_report=quality_report,
            artifacts=PreprocessingArtifacts(),
        )

    @staticmethod
    def _validate_staging_outputs(staging_dir: Path) -> None:
        required_paths = (
            *(staging_dir / filename for filename in REPORT_FILENAMES),
            staging_dir / "extracted_frames",
            staging_dir / "good_frames",
            staging_dir / "blurry_frames",
            staging_dir / "lowest_blur_scores",
            staging_dir / "keyframes",
        )
        missing = [path.name for path in required_paths if not path.exists()]
        if missing:
            raise RuntimeError(f"Preprocessing did not produce required artifacts: {', '.join(missing)}")

    @staticmethod
    def _result_section(result: dict[str, Any], key: str, fallback_path: Path) -> dict[str, Any]:
        value = result.get(key)
        if isinstance(value, dict):
            return value
        with fallback_path.open(encoding="utf-8") as source:
            loaded = json.load(source)
        if not isinstance(loaded, dict):
            raise RuntimeError(f"Preprocessing {key} is not a JSON object")
        return loaded

    @staticmethod
    def _replace_directory(source: Path, destination: Path) -> None:
        if destination.exists():
            if not destination.is_dir():
                raise RuntimeError(f"Expected output directory is not a directory: {destination.name}")
            shutil.rmtree(destination)
        shutil.move(str(source), str(destination))

    @staticmethod
    def _diagnostic(exc: Exception) -> dict[str, str]:
        message = str(exc).strip() or exc.__class__.__name__
        return {"code": "PREPROCESSING_FAILED", "message": message}


__all__ = [
    "PreprocessingFailedError",
    "PreprocessingInProgressError",
    "PreprocessingService",
]
