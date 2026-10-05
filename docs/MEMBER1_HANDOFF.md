# Member 1 — Video Preprocessing Handoff

## Input

Pass a UAV/drone video file to the pipeline. The verified source is:

`data/raw_video/drone_video.mp4`

## Function Entry Point

```python
from src.preprocessing import run_preprocessing

result = run_preprocessing(
    video_path="data/raw_video/drone_video.mp4",
    output_root="output",
    sample_fps=2.0,
    blur_threshold=100.0,
    difference_threshold=12.0,
    enable_stabilization=False,
    decoder="ffmpeg",
)
```

`result` contains the metadata and quality-report dictionaries plus paths to
the generated manifests, keyframes, and (when enabled) stabilized frames.

## Outputs

The supplied `output_root` receives:

- `video_metadata.json` — width, height, FPS, duration, source-frame count,
  and codec when available.
- `frame_metadata.csv` — one traceability row per extracted frame, including
  source-frame index, timestamp, blur score, brightness, acceptance state,
  selection state, and difference score.
- `keyframes/` — original extracted images selected for SfM.
- `keyframes_manifest.csv` — selected keyframe ID, filename, source-frame
  traceability, blur score, and difference score.
- `quality_report.json` — frame counts, retention statistics, blur statistics,
  and the settings used.
- `extracted_frames/`, `good_frames/`, `blurry_frames/`, and
  `lowest_blur_scores/` — intermediate inspection outputs.
- `stabilized_frames/` only when `enable_stabilization=True`.

Stabilized frames are experimental and remain separate. They never replace
the original extracted images used to select SfM keyframes.

## Dependencies

- Python 3
- `opencv-python` (`cv2`)
- `numpy`
- A local FFmpeg installation providing `ffmpeg` and `ffprobe` on `PATH`
  (or configured with `FFMPEG_EXECUTABLE` and `FFPROBE_EXECUTABLE`)

The CSV, JSON, pathlib, and shutil functionality uses the Python standard
library. FFmpeg is a local prerequisite and is never installed by the service.

## Current Experimental Settings

- `sample_fps = 2.0`
- `blur_threshold = 100.0`
- `difference_threshold = 12.0`
- `enable_stabilization = False`

The default decoder uses ffprobe for metadata and FFmpeg for temporal candidate
extraction. Rational FPS values are parsed exactly as floating-point ratios;
metadata unavailable from ffprobe is written as `null`, not guessed. Candidate
source-frame indices are derived from the emitted sampling timestamp and known
source FPS when available. OpenCV remains responsible for Variance of Laplacian
blur scoring, the optional stabilization experiment, and `cv2.absdiff` plus
`np.mean` global keyframe comparison. Set `decoder="opencv"` for the legacy
decoder/sampler benchmark path.

## Verified Result

For the current 1922×1080, 25 FPS, approximately 55-second drone video:

- Source frames: 1375
- Extracted frames: 115
- Usable frames: 115
- Selected keyframes: 72
- Redundant frames skipped: 43

No thresholds were changed to produce this result.
