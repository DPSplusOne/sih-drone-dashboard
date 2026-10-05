# AeroTrace 3D — Team Development Logbook

> **Purpose:** Shared source of truth for current development status, module ownership, handoffs, blockers, decisions, and next actions.
>
> Update this file after every meaningful milestone.
>
> **Do not store passwords, API keys, tokens, credentials, or private data here.**

---

## 1. Project Goal

AeroTrace 3D converts a single-pass UAV video and available telemetry into a georeferenced, measurable 3D digital twin.

### Current target pipeline

```text
UAV Video + GPS / RTK / IMU
        ↓
Adaptive Video Preprocessing
        ↓
Ordered Keyframes
        ↓
COLMAP / Sequential SfM
        ↓
Camera Poses + Sparse 3D Model
        ↓
Dense Reconstruction
        ↓
Optional AI-assisted Recovery
        ↓
GPS / RTK Georeferencing
        ↓
Mesh + Texture
        ↓
Validation
        ↓
3D Tiles / Digital Twin Viewer
```

---

## 2. Current Overall Status

**Last updated:** 05 Oct 2026

### Completed

- FastAPI backend scaffold
- Health API
- Mission/job creation
- Per-job runtime storage
- UAV video upload
- Preprocessing API
- Job lifecycle up to `PREPROCESSED`
- Original OpenCV preprocessing pipeline
- FFmpeg/ffprobe preprocessing-v2 implementation
- OpenCV fallback decoder
- Blur scoring
- Redundancy filtering
- Keyframe manifest generation
- Safe preprocessing reruns
- FFmpeg executable/config detection
- Chunk / parallel extraction architecture
- 23 preprocessing/backend tests passing
- Real FFmpeg single-worker run completed successfully

### Current reference UAV video

- Resolution: **1922 × 1080**
- FPS: **25**
- Duration: **~55 seconds**
- Source frames: **1375**
- Codec: **H.264**

### OpenCV baseline

```text
1375 source
→ 115 sampled
→ 115 usable
→ 72 keyframes
→ 43 redundant skipped
```

Runtime: **~25.18 s**

### FFmpeg preprocessing-v2

```text
1375 source
→ 110 sampled
→ 110 usable
→ 67 keyframes
→ 43 redundant skipped
```

Runtime: **~40.25 s**

Settings:

```text
sample_fps = 2
blur_threshold = 100
difference_threshold = 12
stabilization = false
decoder = ffmpeg
parallel_extraction = false
worker_count = 1
```

### Current observation

FFmpeg's `2 FPS` sampling produces approximately 110 frames for a 55-second video, while the previous OpenCV implementation produced 115 because its frame-interval logic effectively sampled slightly above 2 FPS.

Do **not** change thresholds merely to force the two implementations to return the same frame count.

---

## 3. Branch Status

### `main`

**Purpose:** Stable / submission-ready branch.

**Rule:** Do not merge experimental work directly into `main`.

### `Prachi`

**Purpose:** Integration branch.

**Rule:** Feature branches are merged here only after verification.

### `llama`

**Purpose:** Historical Member 1 preprocessing branch.

**Rule:** Do not use for new preprocessing work.

### `feature/preprocessing-v2`

**Owner:** Prachi

**Purpose:** FFmpeg-based scalable preprocessing upgrade.

**Status:** Implemented and locally validated.

**Completed:**
- FFmpeg / ffprobe support
- OpenCV fallback
- metadata probing
- ordered sampling
- quality filtering
- global keyframe selection
- chunk / overlap architecture
- manifest compatibility
- real-video FFmpeg run
- 23 tests passing

**Pending:**
- parallel FFmpeg benchmark
- COLMAP comparison: 72 OpenCV keyframes vs 67 FFmpeg keyframes
- merge into `Prachi`

---

## 4. Technical Ownership

### Prachi — Integration / Backend / Georeferencing / Deployment

Owns:

- FastAPI architecture
- job lifecycle
- API integration
- branch / merge integration
- telemetry handoff
- georeferencing integration
- deployment architecture
- frontend/backend connection
- CI/CD
- final end-to-end integration

Current priorities:

1. Save and benchmark `feature/preprocessing-v2`
2. Prepare staging deployment
3. Prepare GPS / telemetry integration
4. Integrate downstream modules into `Prachi`

---

### Member 1 — Video Preprocessing

Owns:

```text
UAV video
→ sampling
→ quality analysis
→ candidate frames
→ global keyframe selection
```

Required outputs:

```text
frames/keyframes/

preprocessing/
├── video_metadata.json
├── frame_metadata.csv
├── keyframes_manifest.csv
└── quality_report.json
```

Current architecture:

```text
FFmpeg / OpenCV decoding
→ quality filtering
→ global selection
```

Future scalability:

```text
long video
→ temporal chunks
→ parallel candidate extraction
→ global merge
→ final keyframes
```

Important rule:

- Stabilized frames are **not** used as SfM input.

---

### Member 3 — COLMAP / Structure-from-Motion

Input:

```text
frames/keyframes/
+
preprocessing/keyframes_manifest.csv
```

Owns:

- feature extraction
- sequential matching
- incremental mapping
- bundle adjustment
- camera pose recovery
- sparse 3D reconstruction

Required outputs:

```text
reconstruction/
├── database.db
├── sparse/
├── sparse.ply
├── camera_poses.json
└── sfm_report.json
```

Required metrics:

- input images
- registered images
- registration ratio
- sparse point count
- reprojection error
- runtime
- camera model
- trajectory coherence

Current priority:

Compare:

```text
A. OpenCV keyframes: 72 images
B. FFmpeg keyframes: 67 images
```

Do not change preprocessing thresholds until SfM results are available.

---

### Member 4 — Dense Reconstruction / Final 3D Asset

Input:

- registered images
- COLMAP camera poses
- sparse model

Owns:

```text
Sparse model
→ dense reconstruction / MVS
→ point-cloud cleanup
→ optional AI depth assistance
→ mesh
→ texture
→ final GLB / PLY / OBJ
```

AI depth is **assistive**, not mandatory.

Do not replace SfM/MVS geometry with monocular depth as the primary reconstruction method.

---

## 5. Module Handoffs

### Preprocessing → SfM

Input:

```text
frames/keyframes/
preprocessing/keyframes_manifest.csv
```

Do not rename keyframes after preprocessing.

The manifest preserves:

- filename
- source frame index
- timestamp
- blur score
- difference score

FFmpeg-mode source frame indices may be timestamp-derived; timestamps remain the authoritative temporal reference.

### SfM → Dense Reconstruction

Member 3 provides:

- `camera_poses.json`
- native COLMAP sparse model
- `sparse.ply`
- registered images
- `sfm_report.json`

### Telemetry → Georeferencing

Desired telemetry fields where available:

- timestamp
- latitude
- longitude
- altitude
- RTK / PPK status
- roll
- pitch
- yaw

Join:

```text
keyframes_manifest.csv
+
camera_poses.json
+
telemetry
```

to obtain:

```text
georeferenced camera trajectory
+
metric 3D reconstruction
```

---

## 6. Job Lifecycle

```text
UPLOADED
↓
PREPROCESSING
↓
PREPROCESSED
↓
SFM
↓
SFM_COMPLETED
↓
DENSE_RECONSTRUCTION
↓
DENSE_COMPLETED
↓
GEOREFERENCING
↓
GEOREFERENCED
↓
MESHING
↓
VALIDATION
↓
COMPLETED
```

Failure state:

```text
FAILED
```

---

## 7. Immediate Next Actions

### Priority 1 — Save preprocessing-v2

**Owner:** Prachi

- review `git status`
- review `git diff --stat`
- commit `feature/preprocessing-v2`
- push feature branch
- do not merge into `main`

### Priority 2 — Parallel FFmpeg benchmark

**Owner:** Prachi / Member 1

Test:

```text
parallel_extraction = true
workers = 2
```

Verify:

- chunk planning
- overlap handling
- central merge
- timestamp ordering
- duplicate removal
- global keyframe selection
- runtime

Do not assume parallel mode must outperform single-worker mode on the 55-second reference video.

### Priority 3 — SfM comparison

**Owner:** Member 3

Run COLMAP on:

1. 72 OpenCV-selected keyframes
2. 67 FFmpeg-selected keyframes

Compare:

- registered images
- registration ratio
- sparse points
- reprojection error
- runtime
- trajectory continuity
- sparse-scene coherence

Decision criterion:

Use the preprocessing configuration that provides the best reconstruction-quality / processing-time tradeoff.

### Priority 4 — Dense 3D

**Owner:** Member 4

As soon as one coherent COLMAP sparse model is ready:

- run dense reconstruction
- generate dense point cloud
- preserve camera poses
- test cleanup
- test mesh generation
- export viewer-compatible asset

Do not wait for every preprocessing experiment to finish.

### Priority 5 — Deployment

**Owner:** Prachi

Initial staging deployment target:

```text
Frontend → Vercel
Backend → Railway / equivalent long-running container service
```

Backend container needs:

- Python 3.12
- FastAPI
- FFmpeg
- ffprobe
- OpenCV dependencies
- later COLMAP

Deployment v1 only needs to prove:

```text
public dashboard
→ UAV upload
→ job creation
→ preprocessing
→ real preprocessing metrics
```

COLMAP can be added after local validation.

---

## 8. Frozen Technical Decisions

Do not redesign these without a concrete technical reason.

1. Single-pass means one continuous automated workflow, not literally an unprocessed video stream.
2. Keyframe selection remains part of the system.
3. FFmpeg handles video I/O where useful.
4. OpenCV remains for image-quality analysis.
5. Stabilized frames are not used for SfM.
6. Sequential matching is the default COLMAP strategy for ordered UAV video.
7. AI depth is optional / assistive.
8. GPS/RTK provides real-world scale and georeferencing.
9. Final output should support digital-twin visualization.
10. Experimental development happens on feature branches.

---

## 9. Known Limitations / Open Questions

- FFmpeg single-worker preprocessing is currently slower than the OpenCV baseline on the 55-second reference video.
- Parallel FFmpeg performance is not yet benchmarked.
- OpenCV and FFmpeg currently generate different keyframe counts.
- COLMAP comparison between the 72-frame and 67-frame sets is pending.
- FFmpeg-mode source-frame indices are timestamp-derived.
- GPS/RTK availability for the reference mission must be confirmed.
- Dense reconstruction is not yet validated end-to-end.
- Full cloud reconstruction is not yet deployed.
- Final viewer integration with a real reconstructed model is pending.

---

## 10. Daily / Milestone Entry Template

Copy this section for each meaningful update.

### YYYY-MM-DD — Member / Branch

**Worked on**
- 

**Changed**
- 

**Tested**
- 

**Actual result**
- 

**Output / handoff**
- 

**Blockers**
- 

**Decision made**
- 

**Next action**
- 

**Commit**
`<commit hash or NOT COMMITTED>`

---

## 11. Communication Rules

Before starting work:

1. Fetch the latest remote state.
2. Confirm your own feature branch.
3. Read the latest logbook entry.
4. Check the expected module input/output contract.

After finishing:

1. Run your tests.
2. Record actual results.
3. Update this logbook.
4. Commit your module.
5. Push your feature branch.
6. Inform the integration owner.
7. Do not merge into `main` unless agreed.

Never place in this file:

- passwords
- tokens
- API keys
- private credentials
- personal information
- local `.env` values
