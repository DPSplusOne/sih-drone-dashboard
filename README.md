# AeroTrace 3D

AeroTrace 3D is an SIH26158 project for converting a single-pass drone video, GPS coordinates, and flight metadata into a metrically scaled, georeferenced 3D reconstruction.

The current repository contains a responsive dashboard prototype for the operator workflow: mission input, frame-quality checks, pose and georeferencing progress, reconstruction status, model inspection, validation evidence, and artifact export.

## Current scope

The dashboard remains a static frontend prototype. The backend now provides health checks and Phase 2 mission ingestion: it accepts uploads, creates durable job records, and stores job inputs. Its displayed project data and reconstruction preview remain illustrative until later pipeline stages provide real artifacts and metrics.

## Existing interactions

- Select a drone video and inspect its filename and size
- Reveal optional sensor metadata
- Switch between mesh and point-cloud preview modes
- Simulate final reconstruction-stage completion
- Export a sample validation report
- Use responsive desktop and mobile layouts

## Planned production outputs

- PLY point cloud
- GLB model when textured mesh generation succeeds
- GeoJSON camera track
- JSON validation report with scale, georeferencing, coverage, runtime, and uncertainty evidence

## Documentation

- [Solution overview](docs/solution-plan.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)

## Phase 1 local setup (Windows PowerShell)

Run these commands from the repository root. Python 3.12 is the recommended project interpreter for the upcoming native computer-vision dependencies.

```powershell
# If PowerShell blocks activation in this terminal only:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Create and activate the virtual environment.
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install only the Phase 1 API and test dependencies.
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

Start the API:

```powershell
python -m uvicorn backend.app.main:app --reload
```

- Health endpoint: `http://127.0.0.1:8000/api/health`
- Swagger UI: `http://127.0.0.1:8000/docs`

Run the Phase 1 tests in another terminal with the virtual environment activated:

```powershell
python -m pytest backend\tests
```

Serve the current static frontend from a second terminal:

```powershell
python -m http.server 5500
```

Open `http://127.0.0.1:5500/`. The API allows this local-development origin through CORS.

## Phase 2 job ingestion and preprocessing

Open Swagger at `http://127.0.0.1:8000/docs`, expand `POST /api/jobs`, select **Try it out**, choose the required drone video and any optional files, then select **Execute**.

| Multipart field | Required | Accepted extension |
| --- | --- | --- |
| `video` | Yes | `.mp4`, `.mov`, `.mkv`, `.avi` |
| `gps_csv` | No | `.csv` |
| `imu_csv` | No | `.csv` |
| `metadata_json` | No | `.json` |

The API streams files to disk in chunks; it does not load a whole upload into memory. The default chunk size is 1 MiB and can be changed with `UPLOAD_CHUNK_SIZE`. Extension lists can be configured with `ALLOWED_VIDEO_EXTENSIONS`, `ALLOWED_GPS_EXTENSIONS`, `ALLOWED_IMU_EXTENSIONS`, and `ALLOWED_METADATA_EXTENSIONS` as comma-separated values.

Example PowerShell request:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/jobs `
  -F "video=@C:\capture\single-pass.mp4" `
  -F "gps_csv=@C:\capture\track.csv" `
  -F "metadata_json=@C:\capture\metadata.json"
```

Example response:

```json
{
  "job_id": "0e3c3e24-3bd1-4d42-9c85-6f5d48ac34c8",
  "status": "uploaded",
  "stage": "UPLOADED"
}
```

Each upload is stored under `data/jobs/<job_id>/`. The server keeps fixed input names (`video.<extension>`, `gps.csv`, `imu.csv`, and `metadata.json`) and records the sanitized original filenames, content types, byte counts, timestamps, status, and stage in `job.json`.

Run the verified Member 1 frame-preprocessing stage after upload:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/jobs/<job_id>/preprocess
```

The response and `GET /api/jobs/<job_id>` include a `preprocessing` summary,
including the quality report and job-relative artifact paths. The job moves from
`uploaded`/`UPLOADED`, through `processing`/`PREPROCESSING`, to
`ready`/`PREPROCESSED`. A failed or corrupt video is recorded as
`failed`/`FAILED` with a diagnostic in `error`.

Preprocessing always uses the verified settings: `sample_fps=2.0`,
`blur_threshold=100.0`, `difference_threshold=12.0`, and
`enable_stabilization=false`. Stabilized frames are never used for SfM
keyframe selection. Outputs are kept below the job directory in `frames/`,
`extracted/`, `stabilized/`, `keyframes/`, and `preprocessing/` (the four CSV
and JSON reports).

### FFmpeg preprocessing decoder

Preprocessing defaults to `PREPROCESSING_DECODER=ffmpeg`. Install a local
FFmpeg distribution that provides both `ffmpeg` and `ffprobe`, then make both
commands available on `PATH`, or configure their locations without hard-coded
platform paths:

```powershell
$env:FFMPEG_EXECUTABLE = "ffmpeg"
$env:FFPROBE_EXECUTABLE = "ffprobe"
```

The service does not download or install FFmpeg. A missing executable produces
a recorded preprocessing failure with an installation/configuration message.
`ffprobe` supplies width, height, rational FPS, duration, frame count, and
codec when the container exposes them; unavailable values remain `null` rather
than being invented. FFmpeg extracts ordered candidates at `sample_fps`, then
OpenCV performs the existing Laplacian blur scoring and global frame-difference
keyframe selection.

For old-vs-new decoder benchmarks, set `PREPROCESSING_DECODER=opencv`. The
quality defaults can be configured as `SAMPLE_FPS=2.0`,
`BLUR_THRESHOLD=100.0`, and `DIFFERENCE_THRESHOLD=12.0`; stabilization remains
off by default (`ENABLE_STABILIZATION=false`) and is never used as the SfM
input.
Optional chunk extraction is disabled by default. Its settings are
`PARALLEL_EXTRACTION=false`, `WORKERS=1`, `CHUNK_SECONDS=30`, and
`CHUNK_OVERLAP_SECONDS=1`. When enabled, chunks only extract candidates; the
server merges timestamp-ordered candidates, removes overlap duplicates, and
makes the final keyframe decisions globally.

## Frontend placement

`index.html`, `styles.css`, and `app.js` intentionally remain at the repository root in Phase 1. Moving them before API integration would create unnecessary path churn (including the current documentation link) without improving the visual experience. They will move together into `frontend/` when modular API, pipeline-state, and Three.js viewer code is introduced in a dedicated frontend-integration phase.
