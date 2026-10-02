from __future__ import annotations

import json
from datetime import datetime

from conftest import request


def _video_file(filename: str = "flight.mp4", content: bytes = b"video-bytes"):
    return (filename, content, "video/mp4")


def _create_video_job(test_app):
    response = request(test_app, "POST", "/api/jobs", files={"video": _video_file()})
    assert response.status_code == 201
    return response.json()


def test_create_job_with_video_only(test_app, test_settings) -> None:
    body = _create_video_job(test_app)

    assert body["status"] == "uploaded"
    assert body["stage"] == "UPLOADED"
    assert (test_settings.jobs_dir / body["job_id"] / "input" / "video.mp4").is_file()


def test_create_job_with_video_and_gps(test_app, test_settings) -> None:
    response = request(
        test_app,
        "POST",
        "/api/jobs",
        files={
            "video": _video_file(),
            "gps_csv": ("track.csv", b"timestamp,latitude,longitude\n1,12.1,77.1\n", "text/csv"),
        },
    )

    assert response.status_code == 201
    job_id = response.json()["job_id"]
    assert (test_settings.jobs_dir / job_id / "input" / "gps.csv").read_bytes().startswith(b"timestamp")


def test_rejects_missing_video(test_app, test_settings) -> None:
    response = request(test_app, "POST", "/api/jobs", files={"gps_csv": ("track.csv", b"a,b\n", "text/csv")})

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"
    assert list(test_settings.jobs_dir.iterdir()) == []


def test_rejects_unsupported_video_extension(test_app, test_settings) -> None:
    response = request(test_app, "POST", "/api/jobs", files={"video": _video_file("flight.exe")})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_UPLOAD"
    assert list(test_settings.jobs_dir.iterdir()) == []


def test_get_existing_job(test_app) -> None:
    created = _create_video_job(test_app)

    response = request(test_app, "GET", f"/api/jobs/{created['job_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == created["job_id"]
    assert body["status"] == "uploaded"
    assert body["stage"] == "UPLOADED"
    assert body["progress"] == 0
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    assert body["inputs"]["gps_csv"] is None
    assert body["error"] is None


def test_get_nonexistent_job_returns_404(test_app) -> None:
    response = request(test_app, "GET", "/api/jobs/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "JOB_NOT_FOUND"


def test_uploaded_video_contents_are_written_to_disk(test_app, test_settings) -> None:
    video_content = b"not-a-real-video-but-a-streaming-test"
    response = request(test_app, "POST", "/api/jobs", files={"video": _video_file(content=video_content)})

    job_id = response.json()["job_id"]
    stored_video = test_settings.jobs_dir / job_id / "input" / "video.mp4"
    assert stored_video.read_bytes() == video_content


def test_job_json_is_created_with_upload_metadata(test_app, test_settings) -> None:
    response = request(test_app, "POST", "/api/jobs", files={"video": _video_file("C:\\fakepath\\mission.MP4")})

    job_id = response.json()["job_id"]
    job_record = json.loads((test_settings.jobs_dir / job_id / "job.json").read_text(encoding="utf-8"))
    assert job_record["inputs"]["video"] == {
        "original_filename": "mission.MP4",
        "stored_filename": "video.mp4",
        "size_bytes": len(b"video-bytes"),
        "content_type": "video/mp4",
    }
    assert (test_settings.jobs_dir / job_id / "frames").is_dir()
    assert (test_settings.jobs_dir / job_id / "reconstruction").is_dir()
    assert (test_settings.jobs_dir / job_id / "outputs").is_dir()
    assert (test_settings.jobs_dir / job_id / "logs").is_dir()
