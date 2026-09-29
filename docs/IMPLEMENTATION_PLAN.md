# AeroTrace 3D implementation plan

## 1. Audit snapshot

This audit was completed before implementation work. The repository is a static prototype, not an application with a backend or reconstruction pipeline.

| Path | Current role | Production status |
| --- | --- | --- |
| `index.html` | Entire dashboard document, including sample inputs, stage cards, SVG flight trace, and a hand-drawn SVG model preview | Static/demo-only. It has a video file picker but no form submission, API request, or Three.js canvas. |
| `styles.css` | Polished responsive visual system for the current dashboard | Presentation-only. Preserve its visual language and existing class names during integration. |
| `app.js` | DOM-only interactions: file-name display, metadata toggle, simulated timer-based completion, preview mode classes, and text-report download | Static/demo-only. All progress and displayed values are local hard-coded behavior; there is no network, job, artifact, or error handling. |
| `README.md` | Old Aegis Nexus description | Documentation-only and currently contains literal merge-conflict markers in the working tree. Do not resolve this as part of the backend implementation unless explicitly requested. |
| `docs/solution-plan.md` | Earlier architecture and team-work plan | Documentation-only; useful context but not an executable specification. |

There is no `pyproject.toml`, `requirements` file, `package.json`, test directory, API, Python module, model asset, database, container configuration, or CI workflow. The repository has no Git submodules. As audited on this Windows host, Python 3.14.5 and Node 24.16.0 are installed, but none of the proposed Python libraries are installed. `ffmpeg`, `ffprobe`, `colmap`, `pycolmap`, `nvidia-smi`, and Docker are not on `PATH`; WSL is available. PowerShell execution policy prevents the `npm.ps1` shim from running, although `npm.cmd` can be used if Node tooling is introduced.

### Existing UI integration inventory

Do not redesign the current interface. The first frontend integration should retain the layout and replace values through a small adapter layer.

| Existing element / behavior | Later data source |
| --- | --- |
| Video input and `#upload-title` / `#upload-copy` | Upload response and input-manifest validation result |
| `#video-summary`, `#frames-summary`, `#coverage-summary` | Job metrics and validation report |
| Flight trace, mean altitude, overlap, GPS RMSE | Generated `camera_track.geojson` and trajectory-alignment metrics |
| Pipeline cards, `#pipeline-status`, `#final-stage-copy` | Server-sent job events and persisted stage state |
| Mesh / Points toggle and `#viewer-canvas` | Three.js scene using generated GLB and PLY artifacts |
| Validation card and export button | `validation.json` and signed/downloadable artifact URLs |
| Toast | Upload, queued, progress, completion, cancellation, and error events |

Values that currently claim a duration, frame count, RTK confidence, point count, coverage, reprojection error, geometry quality, or artifact readiness must be replaced with backend results or displayed as unavailable. The simulated `setTimeout` completion must be removed only when real job events are wired in.

## 2. Target architecture

```text
Browser (existing dashboard + modular JavaScript + Three.js)
  | multipart upload, REST reads, Server-Sent Events for job progress
  v
FastAPI API
  | project/job records, input validation, artifact manifests, static frontend
  +--> task queue / worker supervisor
             |
             +--> video worker: FFmpeg + OpenCV
             +--> reconstruction worker: COLMAP / PyCOLMAP
             +--> geometry worker: Open3D (+ GLB packaging)
             +--> validation worker: pyproj + numpy/pandas
  |
  +--> relational metadata store (SQLite for local MVP, PostgreSQL/PostGIS later)
  +--> artifact storage (local work directory for MVP, object storage later)
```

The API is responsible for orchestration and provenance, not for running long GPU jobs in an HTTP request. A job remains resumable after a browser disconnects. Every stage writes an immutable manifest entry with source artifact hashes, command/model version, CRS, timestamps, warning list, and output paths.

### Geospatial contract

1. Preserve source video, original GPS/telemetry timestamps, and any calibration file unchanged.
2. Parse GPS in WGS84 and select a local projected CRS from the capture centroid, normally the appropriate UTM zone. Metric reconstruction, point-cloud processing, and measurement operate only in that projected CRS.
3. Align SfM camera centers to timestamp-matched GPS points with a robust similarity transform (rotation, translation, and scale), rejecting outliers before final bundle adjustment/pose refinement.
4. Record the EPSG code, altitude datum/geoid assumption, transform, residuals, and scale confidence in `geo_alignment.json` and `validation.json`.
5. Treat RTK/PPK as a higher-quality prior, not as an automatic proof of metric accuracy. When GPS coverage is insufficient, publish a model with an explicit `metric_scale_available: false` status rather than a misleading measurement tool.

## 3. Final directory structure

The current root frontend remains intact until its integration phase. The final project can then move the unchanged static assets under `frontend/` in one mechanical commit, avoiding a visual rewrite.

```text
.
├── frontend/
│   ├── index.html                    # existing document, gradually connected
│   ├── styles.css                    # existing design system, retained
│   ├── app.js                        # small bootstrap only
│   ├── modules/
│   │   ├── api.js                    # typed fetch/upload/download client
│   │   ├── job-events.js             # SSE lifecycle and stage state
│   │   ├── dashboard-bindings.js     # maps result JSON to existing cards
│   │   ├── upload-form.js            # video/GPS/IMU/calibration controls
│   │   └── model-viewer.js           # Three.js, GLTFLoader, PLYLoader
│   └── vendor/                       # pinned Three.js build if not bundled
├── backend/
│   ├── aerotrace/
│   │   ├── main.py                   # FastAPI app and static mount
│   │   ├── api/
│   │   │   ├── jobs.py
│   │   │   ├── artifacts.py
│   │   │   └── health.py
│   │   ├── schemas/                  # Pydantic request/result contracts
│   │   ├── services/
│   │   │   ├── ingest.py
│   │   │   ├── video.py
│   │   │   ├── quality.py
│   │   │   ├── reconstruction.py
│   │   │   ├── georeference.py
│   │   │   ├── geometry.py
│   │   │   ├── export.py
│   │   │   └── validation.py
│   │   ├── workers/                  # queue adapter and stage runners
│   │   ├── storage/                  # artifact paths, manifests, hashes
│   │   └── settings.py               # validated binary and work-dir config
│   └── alembic/                      # only after moving beyond SQLite
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/                     # tiny, license-cleared test assets only
│   └── conftest.py
├── scripts/
│   ├── doctor.py                     # diagnose binaries, GPU, package versions
│   └── run_local.ps1                 # local development entry point
├── docs/
│   ├── IMPLEMENTATION_PLAN.md
│   ├── API_CONTRACT.md
│   ├── VALIDATION_PROTOCOL.md
│   └── DEMO_RUNBOOK.md
├── pyproject.toml
├── package.json                      # only if vendor/import-map is not chosen
├── .env.example
└── .gitignore                        # excludes raw inputs, work outputs, secrets
```

Set `AEROTRACE_WORKDIR` to a location outside the repository and OneDrive sync, for example a local SSD work volume. The work directory owns raw uploads, extracted frames, COLMAP databases, dense intermediates, and generated artifacts; Git stores only small fixtures and manifests.

## 4. Runtime dependencies and external tools

### Python environment

Use a dedicated Python 3.12 virtual environment for the first implementation, despite the host having Python 3.14. This is the lowest-risk common target for native computer-vision wheels and PyCOLMAP. Revisit the version only after a clean Windows and Linux installation test.

| Area | Packages | Purpose |
| --- | --- | --- |
| API | `fastapi`, `uvicorn[standard]`, `python-multipart`, `pydantic-settings` | HTTP API, static serving, multipart uploads, configuration |
| Video/CV | `opencv-python-headless`, `numpy`, `scipy` | Decode fallback, blur/duplicate scoring, frame analysis |
| Reconstruction | `pycolmap` | Programmatic COLMAP integration where its wheel/build is supported |
| Geometry | `open3d`, `laspy`, `trimesh` | Point-cloud cleanup, PLY/LAS, mesh inspection and GLB packaging |
| Geospatial | `pandas`, `pyproj` | GPS CSV parsing, timestamp joins, CRS transforms, GeoJSON |
| Reliability | `tenacity`, `structlog` or standard logging | Retries, structured job diagnostics |
| Test | `pytest`, `pytest-asyncio`, `httpx` | Unit, API, and async integration tests |

Pin exact versions in `pyproject.toml` and commit the lock file chosen by the package manager. Do not install packages system-wide. PyCOLMAP should be treated as optional behind a reconstruction adapter: use its wheel when it matches the target platform, otherwise invoke a verified COLMAP binary through `subprocess` with `shell=False`.

### External binaries and configuration

| Tool | Required for | Configuration |
| --- | --- | --- |
| `ffmpeg` and `ffprobe` | Codec-independent metadata inspection, deterministic frame extraction, and sample generation | `FFMPEG_BIN`, `FFPROBE_BIN` |
| COLMAP CLI or compatible PyCOLMAP build | Feature extraction, sequential matching, mapper, dense stereo, fusion, and meshing baseline | `COLMAP_BIN` or `COLMAP_BAT` on Windows |
| NVIDIA driver and CUDA-capable build | Practical dense reconstruction performance | Worker image/runtime, never browser code |
| Optional Blender CLI | Only if required to repair/package a textured GLB after the Open3D stage | `BLENDER_BIN`; do not make it a baseline requirement |

At application startup, `scripts/doctor.py` must print the detected path and `--version` output for FFmpeg, FFprobe, COLMAP, Python packages, GPU driver, and configured work directory. Missing optional tools must produce explicit capability warnings; missing FFmpeg or COLMAP must prevent a job from being queued.

For the initial reconstruction baseline, use COLMAP's sequential workflow: calibrated/estimated intrinsics, feature extraction, sequential matching, sparse mapping and bundle adjustment, image undistortion, patch-match stereo, stereo fusion, and then meshing. Retain the unmodified sparse and dense outputs before Open3D cleaning so every refinement is reversible.

## 5. Input, API, artifact, and progress contracts

### Input contract

`POST /api/v1/jobs` accepts multipart fields:

- `video`: required MP4/MOV input; validate media stream, duration, dimensions, frame rate, and timestamp basis with FFprobe.
- `gps_csv`: required CSV. The documented minimum is `timestamp,latitude,longitude`; `altitude_m` and horizontal/vertical accuracy are optional but strongly recommended.
- `flight_metadata`: optional SRT/CSV/JSON; retain as original evidence and parse only known schemas.
- `imu_csv`: optional timestamped acceleration/angular-rate/orientation data.
- `camera_metadata`: optional JSON/YAML with focal length, sensor size, image dimensions, distortion model, and calibration provenance.
- `rtk_ppk_csv`: optional corrected positions/quality flags; it supersedes non-corrected positions only where timestamps and quality flags are valid.

The response is `202 Accepted` with a stable job ID, an input-validation summary, and an initial `queued` state. Files are streamed to the work directory with size limits and generated server-side names; client filenames are never used as paths.

### Job stages

| State | Work | Persisted outputs |
| --- | --- | --- |
| `validating` | Probe video, parse CSV, verify timestamp coverage and metadata compatibility | `input_manifest.json`, warnings/errors |
| `extracting_frames` | FFmpeg keyframe/time sampling and source-time map | `frames/`, `frame_manifest.json` |
| `filtering_frames` | Blur score, duplicate/overlap score, optional enhancement decision, dynamic masks | selected-frame list, rejected-frame reasons |
| `sparse_reconstruction` | COLMAP features, matches, poses, bundle adjustment, sparse cloud | COLMAP database, `sparse.ply`, `poses.json` |
| `georeferencing` | GPS/IMU matching, robust similarity alignment, projected CRS conversion | `camera_track.geojson`, `geo_alignment.json` |
| `dense_reconstruction` | Undistort, dense stereo, fuse depth/points | `dense_raw.ply` |
| `refining_geometry` | Outlier removal, downsampling, normals, crop/mask dynamic objects, mesh attempt | `dense_clean.ply`, mesh intermediates |
| `exporting` | Create PLY, GLB when textured mesh generation succeeds, GeoJSON, result manifest | downloadable artifact records |
| `validating` | Compute residuals, completeness proxies, runtime and warnings | `validation.json` |
| `completed`, `failed`, `cancelled` | Terminal, never silently overwritten | final event and preserved logs |

`GET /api/v1/jobs/{job_id}` returns the persisted status, stage percentages, warnings, error code/message, metrics, and artifact descriptors. `GET /api/v1/jobs/{job_id}/events` streams state transitions with Server-Sent Events. `GET /api/v1/jobs/{job_id}/artifacts/{artifact_id}` validates access and streams or redirects to the stored output.

`validation.json` must at minimum contain source/job versions, selected CRS, scale/alignment residuals, sparse/dense point counts, usable/rejected frame counts, per-stage runtime, coverage proxy, generated artifact hashes, warnings, and whether metric measurement is safe. It must never report survey-grade accuracy without independent check data.

## 6. Frontend implementation sequence (later, not in this change)

1. Add `api.js`, upload controls for GPS/IMU/camera files, and client-side form validation while retaining the dashboard markup, cards, and CSS.
2. Submit the form, use the returned job ID, and replace the timer simulation with SSE-driven stage updates, retry/cancel actions, and visible failure messages.
3. Add `data-metric` attributes to the existing metric values. `dashboard-bindings.js` then populates only values present in the latest server result; unknown values render `Not available` rather than a demo number.
4. Replace the current SVG-only preview with a Three.js canvas mounted inside `#viewer-canvas`, preserving its card, HUD, toggle buttons, and footer. Load GLB with `GLTFLoader`; load the PLY artifact with `PLYLoader` when a mesh is unavailable. Dispose renderer, geometry, materials, textures, and event handlers when switching jobs.
5. Draw the GeoJSON camera track and confidence/coverage overlay only after confirming both the model and track use the same projected coordinate system.
6. Keep the SVG preview as a zero-data empty state, explicitly labelled as a placeholder, not as a reconstructed result.

The static page must be served by FastAPI or another local HTTP server during integration. Opening it with `file://` is not a supported production mode because API calls, ES modules, and model-asset loading need predictable origins and CORS behavior.

## 7. Platform and operations risks

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Windows host has Python 3.14.5 | Native CV/photogrammetry wheels may not have a compatible Windows wheel at the selected release | Standardize the MVP on Python 3.12 in `.venv`; prove install with `doctor.py` before coding features |
| PyCOLMAP and COLMAP binary compatibility | A PyPI wheel, a source build, and a separately installed COLMAP executable can expose different CUDA/ABI capabilities | Keep an adapter boundary and record the exact engine/version in each manifest |
| CUDA on Windows | Native builds require Visual Studio, CMake, CUDA toolkit, and compatible driver/runtime combinations | Start CPU/small-fixture tests on Windows; run dense GPU jobs in a pinned Linux CUDA worker or WSL2 only after `nvidia-smi` passes |
| WSL2 GPU visibility | WSL availability alone does not prove the NVIDIA driver, GPU forwarding, CUDA toolkit, or disk mount performance | Test GPU inside the chosen runtime; keep artifacts in the Linux filesystem/SSD rather than `/mnt/c` for heavy stages |
| Current repository is in OneDrive | Sync locks, path-length issues, large artifact uploads, and partial files can corrupt or slow active jobs | Keep `AEROTRACE_WORKDIR` outside OneDrive; stage output atomically then publish the manifest |
| Windows command/path handling | COLMAP may be `COLMAP.bat`; paths include spaces; shell concatenation is unsafe | Use `pathlib.Path`, argv lists, `shell=False`, and tested Windows path handling |
| 4K H.265 video and dense reconstruction | Frame extraction, images, COLMAP database, and dense outputs can consume multiples of the original video size and VRAM | Enforce input/disk quotas, keyframe selection, cleanup policy only after artifact retention, and clear estimates in UI |
| Single-pass observation gaps | No algorithm can observe a facade/roof that was not captured | Publish coverage/confidence masks and low-observation warnings; never fabricate measurement-grade geometry |
| GPS altitude and CRS errors | Mixing ellipsoidal/barometric/geoid heights or measuring in degrees causes plausible but wrong output | Require explicit altitude datum assumptions and projected CRS in every result |
| Existing README conflict markers | Unrelated documentation issue can confuse delivery/CI | Preserve now; resolve in a separate, explicit documentation task |

Official references for later setup: [COLMAP installation](https://colmap.github.io/install.html), [PyCOLMAP installation](https://colmap.github.io/pycolmap/index.html), [Open3D build requirements](https://www.open3d.org/docs/latest/compilation.html), and [Three.js GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html).

## 8. Test and acceptance plan

### Automated tests

- Unit: GPS CSV schema and timestamp parsing; UTM selection; coordinate transforms; similarity-transform robustness; blur/duplicate scoring; stage-state transitions; artifact path containment; and validation-report schema.
- API: multipart size/type errors, missing required GPS, malformed metadata, job status reads, cancellation, artifact authorization, and SSE event order.
- Integration: a short license-cleared fixture video and known GPS track run through FFmpeg plus the CPU/small-data path. Assert output manifests, PLY validity, GeoJSON CRS/properties, JSON schema, and expected errors.
- GPU/COLMAP: marked, opt-in tests run only on a provisioned worker. They must not make ordinary `pytest` require CUDA, COLMAP, or a multi-gigabyte dataset.
- Frontend: browser test that uploads fixture files, observes event-driven progress, renders the returned GLB/PLY, and verifies that API metrics replace static text.

### Demonstration acceptance

1. Upload one actual drone video and time-aligned GPS CSV.
2. Show frame rejection counts and reasons, not only the accepted total.
3. Show generated camera track and declared CRS.
4. Load the generated model or point cloud in the viewer.
5. Export PLY, GLB when generated, GeoJSON, and `validation.json`.
6. Show metric scale, alignment residuals, coverage, runtime, and uncertainty/occlusion warnings.
7. Verify at least one known dimension or independent check point before claiming metric accuracy.

## 9. Suggested implementation milestones

1. **Foundation:** create the Python project, settings, `doctor.py`, ignored work directory, data schemas, FastAPI health endpoint, and test harness. Do not touch the existing UI.
2. **Ingest and provenance:** add uploads, input manifests, CSV validation, job persistence, and file-storage safety tests.
3. **Video and sparse baseline:** add FFmpeg/OpenCV keyframe and quality stages, then COLMAP sparse reconstruction and logs.
4. **Georeference and artifacts:** align the trajectory, export sparse PLY and GeoJSON, and generate a validation report before dense processing.
5. **Dense and geometry:** add dense reconstruction, Open3D cleanup, mesh/texturing attempts, and explicit fallback to PLY when GLB cannot be produced reliably.
6. **UI connection:** minimally connect the preserved dashboard to uploads, events, metrics, downloads, and the Three.js viewer.
7. **Validation and deployment:** add test dataset results, hardware matrix, Linux/CUDA worker image, operational limits, and demo runbook.

No application code or existing UI assets are changed by this plan.
