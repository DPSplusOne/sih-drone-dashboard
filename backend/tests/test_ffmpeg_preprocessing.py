"""Unit coverage for the FFmpeg decoder boundary (no FFmpeg installation needed)."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.app.config import Settings
from member1_source import preprocessing
from member1_source.video_io import (
    ExecutableNotFoundError,
    build_ffmpeg_sampling_command,
    extract_frames_ffmpeg,
    inspect_video_ffprobe,
    merge_candidate_records,
    parse_rational,
    plan_chunks,
    resolve_executable,
)


def test_ffmpeg_executable_resolution_uses_path(monkeypatch) -> None:
    monkeypatch.setattr("member1_source.video_io.shutil.which", lambda command: "/tools/ffmpeg")

    assert resolve_executable("ffmpeg", "ffmpeg") == "/tools/ffmpeg"


def test_ffprobe_executable_resolution_uses_path(monkeypatch) -> None:
    monkeypatch.setattr("member1_source.video_io.shutil.which", lambda command: "/tools/ffprobe")

    assert resolve_executable("ffprobe", "ffprobe") == "/tools/ffprobe"


def test_missing_ffmpeg_has_a_controlled_error(monkeypatch) -> None:
    monkeypatch.setattr("member1_source.video_io.shutil.which", lambda command: None)

    with pytest.raises(ExecutableNotFoundError, match="FFMPEG_EXECUTABLE"):
        resolve_executable("ffmpeg", "ffmpeg")


def test_ffmpeg_extraction_fails_cleanly_when_the_tool_is_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("member1_source.video_io.shutil.which", lambda command: None)

    with pytest.raises(ExecutableNotFoundError, match="FFMPEG_EXECUTABLE"):
        extract_frames_ffmpeg(
            tmp_path / "mission.mp4",
            tmp_path / "extracted",
            {"fps": 25.0, "duration_seconds": 1.0, "source_frame_count": 25},
        )


def test_ffmpeg_and_chunk_settings_are_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("FFMPEG_EXECUTABLE", "custom-ffmpeg")
    monkeypatch.setenv("FFPROBE_EXECUTABLE", "custom-ffprobe")
    monkeypatch.setenv("PREPROCESSING_DECODER", "opencv")
    monkeypatch.setenv("SAMPLE_FPS", "3")
    monkeypatch.setenv("BLUR_THRESHOLD", "90")
    monkeypatch.setenv("DIFFERENCE_THRESHOLD", "11")
    monkeypatch.setenv("ENABLE_STABILIZATION", "false")
    monkeypatch.setenv("PARALLEL_EXTRACTION", "true")
    monkeypatch.setenv("WORKERS", "3")
    monkeypatch.setenv("CHUNK_SECONDS", "20")
    monkeypatch.setenv("CHUNK_OVERLAP_SECONDS", "0.5")

    settings = Settings.from_environment()

    assert settings.ffmpeg_executable == "custom-ffmpeg"
    assert settings.ffprobe_executable == "custom-ffprobe"
    assert settings.preprocessing_decoder == "opencv"
    assert settings.sample_fps == 3.0
    assert settings.blur_threshold == 90.0
    assert settings.difference_threshold == 11.0
    assert settings.enable_stabilization is False
    assert settings.parallel_extraction is True
    assert settings.preprocessing_workers == 3
    assert settings.chunk_seconds == 20.0
    assert settings.chunk_overlap_seconds == 0.5


def test_ffprobe_metadata_parsing_and_rational_fps(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("member1_source.video_io.resolve_executable", lambda executable, tool: executable)
    payload = {
        "streams": [
            {
                "width": 1922,
                "height": 1080,
                "avg_frame_rate": "30000/1001",
                "r_frame_rate": "30/1",
                "nb_frames": "1375",
                "codec_name": "h264",
            }
        ],
        "format": {"duration": "55.0"},
    }
    monkeypatch.setattr(
        "member1_source.video_io.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, json.dumps(payload), ""),
    )

    metadata = inspect_video_ffprobe(tmp_path / "mission.mp4")

    assert metadata == {
        "width": 1922,
        "height": 1080,
        "fps": pytest.approx(30000 / 1001),
        "duration_seconds": 55.0,
        "source_frame_count": 1375,
        "codec": "h264",
    }
    assert parse_rational("30000/1001") == pytest.approx(30000 / 1001)
    assert parse_rational("0/0") is None


def test_ffmpeg_sampling_command_contains_sampling_and_optional_chunk_range(tmp_path) -> None:
    command = build_ffmpeg_sampling_command(
        "ffmpeg",
        tmp_path / "input.mp4",
        tmp_path / "out" / "frame_%05d.jpg",
        2.0,
        start_seconds=29.0,
        duration_seconds=26.0,
    )

    assert command[:8] == ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "29.000000", "-i"]
    assert "fps=fps=2" in command
    assert command[command.index("-t") + 1] == "26.000000"
    assert command[-1].endswith("frame_%05d.jpg")


def _candidate(path: Path, timestamp: float, chunk_id: int = 0) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"frame")
    return {
        "path": str(path),
        "timestamp_seconds": timestamp,
        "source_frame_index": round(timestamp * 25),
        "chunk_id": chunk_id,
        "decoder": "ffmpeg",
    }


def test_merge_orders_candidates_and_removes_overlap_duplicates(tmp_path) -> None:
    candidates = [
        _candidate(tmp_path / "one.jpg", 1.0, 1),
        _candidate(tmp_path / "zero.jpg", 0.0, 0),
        _candidate(tmp_path / "overlap.jpg", 1.0, 0),
        _candidate(tmp_path / "two.jpg", 2.0, 1),
    ]

    records = merge_candidate_records(candidates, tmp_path / "extracted")

    assert [record["filename"] for record in records] == ["frame_00000.jpg", "frame_00001.jpg", "frame_00002.jpg"]
    assert [record["timestamp_seconds"] for record in records] == [0.0, 1.0, 2.0]
    assert [record["source_frame_index"] for record in records] == [0, 25, 50]
    assert all((tmp_path / "extracted" / record["filename"]).is_file() for record in records)
    assert not (tmp_path / "overlap.jpg").exists()


def test_chunk_planning_provides_adjacent_overlap() -> None:
    chunks = plan_chunks(55.0, chunk_seconds=30.0, chunk_overlap_seconds=1.0)

    assert chunks == [
        {"chunk_id": 0, "start_seconds": 0.0, "duration_seconds": 31.0},
        {"chunk_id": 1, "start_seconds": 29.0, "duration_seconds": 26.0},
    ]


def _write_sharp_image(path: Path, offset: int) -> None:
    image = np.zeros((180, 320, 3), dtype=np.uint8)
    image[:, offset : offset + 80] = 255
    assert cv2.imwrite(str(path), image)


def test_manifests_and_quality_report_remain_compatible_with_ffmpeg_candidates(monkeypatch, tmp_path) -> None:
    def fake_inspect(*args, **kwargs):
        return {
            "width": 320,
            "height": 180,
            "fps": 25.0,
            "duration_seconds": 1.0,
            "source_frame_count": 25,
            "codec": "h264",
        }

    def fake_extract(video_path, output_folder, metadata, sample_fps, *args, **kwargs):
        output = Path(output_folder)
        output.mkdir(parents=True)
        _write_sharp_image(output / "frame_00000.jpg", 10)
        _write_sharp_image(output / "frame_00001.jpg", 130)
        return [
            {"filename": "frame_00000.jpg", "source_frame_index": 0, "timestamp_seconds": 0.0, "chunk_id": 0, "decoder": "ffmpeg"},
            {"filename": "frame_00001.jpg", "source_frame_index": 12, "timestamp_seconds": 0.5, "chunk_id": 0, "decoder": "ffmpeg"},
        ]

    monkeypatch.setattr(preprocessing, "inspect_video_ffprobe", fake_inspect)
    monkeypatch.setattr(preprocessing, "extract_frames_ffmpeg", fake_extract)

    result = preprocessing.run_preprocessing(
        tmp_path / "mission.mp4", tmp_path / "output", decoder="ffmpeg", difference_threshold=1.0
    )

    with (tmp_path / "output" / "frame_metadata.csv").open(newline="", encoding="utf-8") as source:
        frame_rows = list(csv.DictReader(source))
    with (tmp_path / "output" / "keyframes_manifest.csv").open(newline="", encoding="utf-8") as source:
        manifest_rows = list(csv.DictReader(source))

    assert {"filename", "source_frame_index", "timestamp_seconds", "blur_score", "difference_score"} <= set(frame_rows[0])
    assert set(manifest_rows[0]) == {
        "keyframe_id", "filename", "source_frame_index", "timestamp_seconds", "blur_score", "difference_score"
    }
    assert [float(row["timestamp_seconds"]) for row in frame_rows] == [0.0, 0.5]
    report = result["quality_report"]
    assert report["source_frames"] == 25
    assert report["extracted_frames"] == 2
    assert report["decoder"] == "ffmpeg"
    assert report["parallel_extraction"] is False
    assert report["worker_count"] == 1
    assert report["runtime_seconds"] >= 0
