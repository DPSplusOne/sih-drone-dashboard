from __future__ import annotations

import json
from pathlib import Path

from conftest import request


def _video_file(filename: str = "flight.mp4", content: bytes = b"video-bytes"):
    return (filename, content, "video/mp4")


def _create_video_job(test_app) -> str:
    response = request(test_app, "POST", "/api/jobs", files={"video": _video_file()})
    assert response.status_code == 201
    return response.json()["job_id"]


def _fake_preprocessing(run_number: int, observed_states: list[tuple[str, str]] | None = None):
    """Return a Member 1-shaped result without running the OpenCV algorithm in API tests."""

    def run_preprocessing(**kwargs):
        output_root = Path(kwargs["output_root"])
        job_dir = output_root.parent
        if observed_states is not None:
            record = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
            observed_states.append((record["status"], record["stage"]))

        assert kwargs["sample_fps"] == 2.0
        assert kwargs["blur_threshold"] == 100.0
        assert kwargs["difference_threshold"] == 12.0
        assert kwargs["enable_stabilization"] is False

        for directory_name in (
            "extracted_frames",
            "good_frames",
            "blurry_frames",
            "lowest_blur_scores",
            "keyframes",
        ):
            (output_root / directory_name).mkdir(parents=True, exist_ok=True)

        (output_root / "extracted_frames" / f"extracted-{run_number}.jpg").write_bytes(b"frame")
        (output_root / "good_frames" / f"accepted-{run_number}.jpg").write_bytes(b"frame")
        (output_root / "keyframes" / f"keyframe-{run_number}.jpg").write_bytes(b"frame")
        video_metadata = {"width": 1922, "height": 1080, "fps": 25.0, "source_frame_count": 1375}
        quality_report = {
            "source_frames": 1375,
            "extracted_frames": 115,
            "usable_frames": 115,
            "blur_rejected": 0,
            "selected_keyframes": 72,
            "redundant_skipped": 43,
            "retention_percentage": 62.6086956522,
            "sample_fps": 2.0,
            "blur_threshold": 100.0,
            "difference_threshold": 12.0,
        }
        (output_root / "video_metadata.json").write_text(json.dumps(video_metadata), encoding="utf-8")
        (output_root / "frame_metadata.csv").write_text("filename\\n", encoding="utf-8")
        (output_root / "keyframes_manifest.csv").write_text("filename\\n", encoding="utf-8")
        (output_root / "quality_report.json").write_text(json.dumps(quality_report), encoding="utf-8")
        return {"video_metadata": video_metadata, "quality_report": quality_report}

    return run_preprocessing


def test_preprocess_valid_job_persists_summary_and_artifacts(test_app, test_settings, monkeypatch) -> None:
    observed_states: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "backend.app.services.preprocessing_service._run_preprocessing",
        _fake_preprocessing(run_number=1, observed_states=observed_states),
    )
    job_id = _create_video_job(test_app)

    response = request(test_app, "POST", f"/api/jobs/{job_id}/preprocess")

    assert response.status_code == 200
    body = response.json()
    assert observed_states == [("processing", "PREPROCESSING")]
    assert body["job_id"] == job_id
    assert body["status"] == "ready"
    assert body["stage"] == "PREPROCESSED"
    assert body["preprocessing"]["quality_report"]["source_frames"] == 1375
    assert body["preprocessing"]["quality_report"]["extracted_frames"] == 115
    assert body["preprocessing"]["quality_report"]["selected_keyframes"] == 72
    assert body["preprocessing"]["settings"] == {
        "sample_fps": 2.0,
        "blur_threshold": 100.0,
        "difference_threshold": 12.0,
        "enable_stabilization": False,
    }
    assert body["preprocessing"]["artifacts"]["keyframes_dir"] == "keyframes"

    job_dir = test_settings.jobs_dir / job_id
    assert (job_dir / "frames" / "accepted-1.jpg").is_file()
    assert (job_dir / "extracted" / "extracted-1.jpg").is_file()
    assert (job_dir / "stabilized").is_dir()
    assert list((job_dir / "stabilized").iterdir()) == []
    assert (job_dir / "keyframes" / "keyframe-1.jpg").is_file()
    for filename in (
        "video_metadata.json",
        "frame_metadata.csv",
        "keyframes_manifest.csv",
        "quality_report.json",
    ):
        assert (job_dir / "preprocessing" / filename).is_file()

    persisted = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "ready"
    assert persisted["stage"] == "PREPROCESSED"
    assert persisted["preprocessing"] == body["preprocessing"]

    get_response = request(test_app, "GET", f"/api/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["preprocessing"] == body["preprocessing"]


def test_preprocess_unknown_job_returns_404(test_app) -> None:
    response = request(test_app, "POST", "/api/jobs/00000000-0000-0000-0000-000000000000/preprocess")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "JOB_NOT_FOUND"


def test_preprocess_failure_marks_corrupt_video_job_failed(test_app, test_settings) -> None:
    response = request(
        test_app,
        "POST",
        "/api/jobs",
        files={"video": _video_file(filename="corrupt.mp4", content=b"not-a-valid-video")},
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    response = request(test_app, "POST", f"/api/jobs/{job_id}/preprocess")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PREPROCESSING_FAILED"
    assert "Could not open video" in response.json()["detail"]["message"]
    persisted = json.loads((test_settings.jobs_dir / job_id / "job.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "failed"
    assert persisted["stage"] == "FAILED"
    assert persisted["error"] == response.json()["detail"]
    assert persisted["preprocessing"] is None


def test_preprocess_can_be_rerun_safely(test_app, test_settings, monkeypatch) -> None:
    job_id = _create_video_job(test_app)
    monkeypatch.setattr("backend.app.services.preprocessing_service._run_preprocessing", _fake_preprocessing(run_number=1))
    first_response = request(test_app, "POST", f"/api/jobs/{job_id}/preprocess")
    assert first_response.status_code == 200

    monkeypatch.setattr("backend.app.services.preprocessing_service._run_preprocessing", _fake_preprocessing(run_number=2))
    second_response = request(test_app, "POST", f"/api/jobs/{job_id}/preprocess")

    assert second_response.status_code == 200
    job_dir = test_settings.jobs_dir / job_id
    assert not (job_dir / "extracted" / "extracted-1.jpg").exists()
    assert (job_dir / "extracted" / "extracted-2.jpg").is_file()
    assert not (job_dir / "keyframes" / "keyframe-1.jpg").exists()
    assert (job_dir / "keyframes" / "keyframe-2.jpg").is_file()
    assert json.loads((job_dir / "job.json").read_text(encoding="utf-8"))["stage"] == "PREPROCESSED"
