"""Video inspection and candidate-frame extraction backends.

This module deliberately has no OpenCV dependency.  It keeps process handling,
FFmpeg command construction, and chunk merging separate from the image-quality
and keyframe-selection operations in :mod:`preprocessing`.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Iterable


class VideoToolError(RuntimeError):
    """Base error for an unavailable or failed external video tool."""


class ExecutableNotFoundError(VideoToolError):
    """Raised when an explicitly configured or PATH-resolved tool is missing."""


def resolve_executable(executable: str | Path, tool_name: str) -> str:
    """Resolve a configured command without guessing platform-specific paths."""

    configured = str(executable).strip()
    if not configured:
        raise ExecutableNotFoundError(
            f"{tool_name} executable is not configured. Set {tool_name.upper()}_EXECUTABLE."
        )

    candidate = Path(configured).expanduser()
    if candidate.parent != Path("."):
        if candidate.is_file():
            return str(candidate)
    else:
        resolved = shutil.which(configured)
        if resolved:
            return resolved

    raise ExecutableNotFoundError(
        f"{tool_name} executable not found: {configured}. "
        f"Install FFmpeg and set {tool_name.upper()}_EXECUTABLE, or add it to PATH."
    )


def parse_rational(value: str | int | float | None) -> float | None:
    """Parse an ffprobe rational value without rounding NTSC frame rates."""

    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        if "/" in text:
            numerator_text, denominator_text = text.split("/", maxsplit=1)
            numerator = float(numerator_text)
            denominator = float(denominator_text)
            if denominator == 0:
                return None
            return numerator / denominator
        return float(text)
    except (TypeError, ValueError):
        return None


def _number_or_none(value: Any, number_type: type[int] | type[float]) -> int | float | None:
    if value is None or str(value).upper() == "N/A":
        return None
    try:
        return number_type(value)
    except (TypeError, ValueError):
        return None


def build_ffprobe_command(ffprobe_executable: str, video_path: Path) -> list[str]:
    """Build the JSON-only ffprobe invocation used for the stable metadata schema."""

    return [
        ffprobe_executable,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,codec_name,duration:format=duration",
        "-of",
        "json",
        str(video_path),
    ]


def parse_ffprobe_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the existing video-metadata fields from an ffprobe JSON payload.

    ``None`` represents unavailable data; the function intentionally does not
    infer duration or frame count from another field.
    """

    streams = payload.get("streams")
    stream = streams[0] if isinstance(streams, list) and streams else {}
    if not isinstance(stream, dict):
        stream = {}
    format_data = payload.get("format")
    if not isinstance(format_data, dict):
        format_data = {}

    fps = parse_rational(stream.get("avg_frame_rate"))
    if fps is None:
        fps = parse_rational(stream.get("r_frame_rate"))
    duration = _number_or_none(format_data.get("duration"), float)
    if duration is None:
        duration = _number_or_none(stream.get("duration"), float)

    return {
        "width": _number_or_none(stream.get("width"), int),
        "height": _number_or_none(stream.get("height"), int),
        "fps": fps,
        "duration_seconds": duration,
        "source_frame_count": _number_or_none(stream.get("nb_frames"), int),
        "codec": stream.get("codec_name") or None,
    }


def inspect_video_ffprobe(video_path: str | Path, ffprobe_executable: str = "ffprobe") -> dict[str, Any]:
    """Inspect the first video stream with ffprobe and preserve missing values."""

    video = Path(video_path)
    resolved = resolve_executable(ffprobe_executable, "ffprobe")
    command = build_ffprobe_command(resolved, video)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise VideoToolError(f"Could not run ffprobe: {exc}") from exc
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout or "unknown ffprobe error").strip()
        raise VideoToolError(f"ffprobe failed for {video.name}: {diagnostic}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VideoToolError(f"ffprobe returned invalid JSON for {video.name}") from exc
    if not isinstance(payload, dict):
        raise VideoToolError(f"ffprobe returned an unexpected payload for {video.name}")
    return parse_ffprobe_metadata(payload)


def build_ffmpeg_sampling_command(
    ffmpeg_executable: str,
    video_path: str | Path,
    output_pattern: str | Path,
    sample_fps: float,
    *,
    start_seconds: float | None = None,
    duration_seconds: float | None = None,
) -> list[str]:
    """Build a deterministic FFmpeg image-sequence extraction command."""

    if sample_fps <= 0:
        raise ValueError("sample_fps must be greater than zero.")
    command = [ffmpeg_executable, "-hide_banner", "-loglevel", "error", "-y"]
    if start_seconds is not None:
        command.extend(["-ss", f"{start_seconds:.6f}"])
    command.extend(["-i", str(video_path)])
    if duration_seconds is not None:
        command.extend(["-t", f"{duration_seconds:.6f}"])
    command.extend(
        [
            "-map",
            "0:v:0",
            "-vf",
            f"fps=fps={sample_fps:.12g}",
            "-q:v",
            "2",
            "-start_number",
            "0",
            str(output_pattern),
        ]
    )
    return command


def _clear_folder(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for path in folder.iterdir():
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def _source_frame_index(timestamp_seconds: float, source_fps: float | None, source_frame_count: int | None) -> int | None:
    """Derive an index only from known timing information, never by guessing."""

    if source_fps is None or source_fps <= 0:
        return None
    index = int(math.floor(timestamp_seconds * source_fps + 0.5))
    if source_frame_count is not None and source_frame_count > 0:
        index = min(index, source_frame_count - 1)
    return index


def _frames_in(folder: Path) -> list[Path]:
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"})


def _extract_ffmpeg_chunk(
    video_path: str,
    output_folder: str,
    sample_fps: float,
    ffmpeg_executable: str,
    start_seconds: float,
    duration_seconds: float | None,
    chunk_id: int,
    source_fps: float | None,
    source_frame_count: int | None,
) -> list[dict[str, Any]]:
    """Worker-safe candidate extraction; keyframe selection stays central."""

    folder = Path(output_folder)
    _clear_folder(folder)
    resolved = resolve_executable(ffmpeg_executable, "ffmpeg")
    command = build_ffmpeg_sampling_command(
        resolved,
        video_path,
        folder / "candidate_%06d.jpg",
        sample_fps,
        start_seconds=start_seconds,
        duration_seconds=duration_seconds,
    )
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise VideoToolError(f"Could not run ffmpeg: {exc}") from exc
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout or "unknown ffmpeg error").strip()
        raise VideoToolError(f"ffmpeg frame extraction failed: {diagnostic}")

    records: list[dict[str, Any]] = []
    for ordinal, frame_path in enumerate(_frames_in(folder)):
        # The fps filter emits a regular sequence.  The index is derived from
        # that output timestamp and the ffprobe source FPS when it is known.
        timestamp_seconds = start_seconds + ordinal / sample_fps
        records.append(
            {
                "path": str(frame_path),
                "timestamp_seconds": timestamp_seconds,
                "source_frame_index": _source_frame_index(
                    timestamp_seconds, source_fps, source_frame_count
                ),
                "chunk_id": chunk_id,
                "decoder": "ffmpeg",
            }
        )
    return records


def plan_chunks(
    duration_seconds: float | None,
    chunk_seconds: float,
    chunk_overlap_seconds: float,
) -> list[dict[str, float | int | None]]:
    """Plan overlapping decode ranges while keeping each chunk's core contiguous."""

    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be greater than zero.")
    if chunk_overlap_seconds < 0:
        raise ValueError("chunk_overlap_seconds cannot be negative.")
    if duration_seconds is None or duration_seconds <= 0:
        return [{"chunk_id": 0, "start_seconds": 0.0, "duration_seconds": None}]

    chunks: list[dict[str, float | int | None]] = []
    core_start = 0.0
    chunk_id = 0
    while core_start < duration_seconds:
        core_end = min(core_start + chunk_seconds, duration_seconds)
        start = max(0.0, core_start - (chunk_overlap_seconds if chunk_id else 0.0))
        end = min(duration_seconds, core_end + chunk_overlap_seconds)
        chunks.append(
            {
                "chunk_id": chunk_id,
                "start_seconds": start,
                "duration_seconds": max(0.0, end - start),
            }
        )
        core_start = core_end
        chunk_id += 1
    return chunks


def merge_candidate_records(
    candidates: Iterable[dict[str, Any]],
    destination_folder: str | Path,
    *,
    duplicate_tolerance_seconds: float = 1e-6,
) -> list[dict[str, Any]]:
    """Globally order chunk candidates, remove overlap duplicates, and rename once."""

    if duplicate_tolerance_seconds < 0:
        raise ValueError("duplicate_tolerance_seconds cannot be negative.")
    destination = Path(destination_folder)
    _clear_folder(destination)
    ordered = sorted(candidates, key=lambda item: (float(item["timestamp_seconds"]), int(item.get("chunk_id", 0))))
    merged: list[dict[str, Any]] = []
    previous_timestamp: float | None = None
    for candidate in ordered:
        timestamp = float(candidate["timestamp_seconds"])
        if previous_timestamp is not None and abs(timestamp - previous_timestamp) <= duplicate_tolerance_seconds:
            continue
        source = Path(str(candidate["path"]))
        if not source.is_file():
            raise VideoToolError(f"FFmpeg candidate frame is missing: {source}")
        filename = f"frame_{len(merged):05d}.jpg"
        shutil.move(str(source), str(destination / filename))
        merged.append(
            {
                "filename": filename,
                "source_frame_index": candidate.get("source_frame_index"),
                "timestamp_seconds": timestamp,
                "chunk_id": candidate.get("chunk_id"),
                "decoder": candidate.get("decoder", "ffmpeg"),
            }
        )
        previous_timestamp = timestamp
    return merged


def extract_frames_ffmpeg(
    video_path: str | Path,
    output_folder: str | Path,
    metadata: dict[str, Any],
    sample_fps: float = 2.0,
    ffmpeg_executable: str = "ffmpeg",
    *,
    parallel_extraction: bool = False,
    workers: int = 1,
    chunk_seconds: float = 30.0,
    chunk_overlap_seconds: float = 1.0,
) -> list[dict[str, Any]]:
    """Extract ordered FFmpeg candidates and centralize all overlap handling."""

    if sample_fps <= 0:
        raise ValueError("sample_fps must be greater than zero.")
    if workers < 1:
        raise ValueError("workers must be at least one.")
    video = Path(video_path)
    output = Path(output_folder)
    resolved = resolve_executable(ffmpeg_executable, "ffmpeg")
    chunks = plan_chunks(metadata.get("duration_seconds"), chunk_seconds, chunk_overlap_seconds)
    if not parallel_extraction:
        chunks = [{"chunk_id": 0, "start_seconds": 0.0, "duration_seconds": None}]

    candidates_root = output.parent / f".{output.name}-candidates"
    _clear_folder(candidates_root)
    tasks = [
        (
            str(video),
            str(candidates_root / f"chunk_{int(chunk['chunk_id']):04d}"),
            sample_fps,
            resolved,
            float(chunk["start_seconds"]),
            None if chunk["duration_seconds"] is None else float(chunk["duration_seconds"]),
            int(chunk["chunk_id"]),
            metadata.get("fps"),
            metadata.get("source_frame_count"),
        )
        for chunk in chunks
    ]
    try:
        if parallel_extraction and len(tasks) > 1:
            with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as executor:
                futures = [executor.submit(_extract_ffmpeg_chunk, *task) for task in tasks]
                groups = [future.result() for future in futures]
        else:
            groups = [_extract_ffmpeg_chunk(*task) for task in tasks]
        candidates = [record for group in groups for record in group]
        return merge_candidate_records(candidates, output)
    finally:
        if candidates_root.exists():
            shutil.rmtree(candidates_root)


__all__ = [
    "ExecutableNotFoundError",
    "VideoToolError",
    "build_ffmpeg_sampling_command",
    "build_ffprobe_command",
    "extract_frames_ffmpeg",
    "inspect_video_ffprobe",
    "merge_candidate_records",
    "parse_ffprobe_metadata",
    "parse_rational",
    "plan_chunks",
    "resolve_executable",
]
