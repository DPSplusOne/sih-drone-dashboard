# AeroTrace 3D — SIH26158 solution plan

## Product promise

Convert one continuous drone-video pass into a **georeferenced, measurable 3D deliverable**: a textured mesh, dense point cloud, camera trajectory, coverage/confidence map, and validation report. The system must show uncertainty instead of inventing geometry in poorly observed or occluded areas.

The dashboard in this repository is the operator/demo client. It demonstrates job intake, pipeline state, 3D-output inspection, and export/validation evidence. GPU reconstruction runs in a separate worker service; a browser alone should not be presented as the photogrammetry engine.

## Scope extracted from the problem statement

Required input: 1080p/4K drone video, GPS coordinates, and flight metadata. Optional input: IMU, barometric altitude, camera intrinsics, and RTK/PPK corrections.

Required result: a georeferenced and metrically accurate representation of terrain, structures, facades/roofs, roads/infrastructure, vegetation/obstacles, as textured mesh or point cloud, usable for visualization, measurement, and analysis.

Primary risks to design for: single-path view gaps, motion/compression blur, illumination changes, moving objects, noisy GPS, near-real-time limits, occlusion, and accuracy without many ground-control points.

## Architecture

```text
Web client
  upload video + telemetry; inspect model; measure/export
        |
API / job orchestrator
  asset store, job state, access control, provenance
        |
GPU workers -------------------------------------------------------------+
  1. condition frames       -> quality scores, masks, selected frames   |
  2. estimate poses         -> VO/SLAM + bundle adjustment              |
  3. align to world         -> GPS/IMU/RTK fusion, EPSG transform       |
  4. reconstruct geometry   -> matching + depth priors + dense fusion   |
  5. refine surface         -> dynamic filtering, occlusion confidence  |
  6. texture and validate   -> GLB/LAS/GeoJSON + report                 |
        |                                                               |
Object storage <--- frames, trajectory, cloud, mesh, masks, metrics ---+
```

Recommended production stack: React/Three.js viewer; FastAPI API; PostgreSQL/PostGIS for projects, tracks, measurements, and spatial metadata; S3-compatible object storage; Redis/Celery or a workflow runner for jobs; Dockerized CUDA worker images. Start with COLMAP or OpenMVG/OpenMVS for SfM/MVS baselines, OpenCV for video/quality processing, and PDAL/Open3D/MeshLab tooling for point cloud/mesh post-processing. Replace individual components only after they are benchmarked against the baseline.

### Geographic and metric contract

- Preserve original EXIF/SRT/telemetry and record source timestamps.
- Store WGS84 input coordinates, and process local geometry in a declared projected CRS (UTM chosen from the capture centroid). Never measure distances in latitude/longitude degrees.
- Emit the CRS/EPSG, geoid/altitude reference, coordinate transform, calibration version, and code/model version in every result manifest.
- Use GPS/IMU/RTK as priors in bundle adjustment, not as unverified camera positions. Estimate and report residuals.
- Each mesh face/point needs a confidence value derived from observation count, viewing angle, reprojection error, depth uncertainty, and dynamic/occlusion masks.

## End-to-end pipeline and acceptance evidence

| Stage | Owner | Implemented output | Gate before next stage |
| --- | --- | --- | --- |
| Frame conditioning | Member 1 | Keyframes, blur/compression score, exposure-normalized frames, dynamic masks | Enough sharp, temporally diverse frames; rejection reasons saved |
| Pose + world alignment | Member 2 | Calibrated poses, sparse cloud, trajectory, CRS transform | Bundle-adjustment reprojection RMSE and GPS residual within test threshold |
| Depth + dense fusion | Member 3 | Pair graph, depth confidence, dense colored point cloud | Coverage/point density meets visible-scene threshold |
| Surface cleanup | Member 4 | Filtered cloud, mesh, texture atlas, occlusion-confidence mask | No dynamic-object remnants; low-observation zones visibly flagged |
| Validation | Member 5 | Accuracy, completeness, runtime, robustness report | Compare with held-out checkpoints/known dimensions and a reference model |
| Demo + delivery | Member 6 | Dataset script, demo flow, PPT, architecture, reproducibility guide | Fresh-machine run demonstrates ingest → result → measure → report |

## What to implement first (MVP)

1. **Reproducible ingest:** accept MP4/MOV and GPS/SRT/CSV; validate timestamps, parse metadata, retain an immutable manifest, and show actionable missing-data warnings.
2. **Baseline reconstruction:** extract quality-filtered keyframes, calibrate/fix camera intrinsics, run sequential SfM and bundle adjustment, align with GPS/RTK, and export a sparse/dense cloud.
3. **Evidence-first viewer:** load LAS/PLY and GLB; show CRS, trajectory, measurement tool, observation/coverage layer, and errors—not only a beauty render.
4. **Single-pass robustness:** add optical-flow/keyframe diversity scoring, motion deblurring only when it improves matching, illumination normalization, semantic masks for vehicles/people, and monocular depth priors only as regularizers.
5. **Validation:** use a small controlled site with surveyed control/check points and known dimensions. Maintain holdout flights and stress sets for blur, shadows, vegetation, and weak GPS.

## Metrics to put in the scorecard

- Check-point horizontal/vertical RMSE and 3D distance error (meters)
- Median and P95 reprojection error (pixels)
- Absolute scale error against known distances (%)
- Visible-surface completeness and texture coverage (%)
- Percentage of low-confidence/occluded area correctly flagged
- Dynamic-object false-retention rate
- Processing time per input-video minute and peak GPU/VRAM usage
- Robustness deltas for blur, compression, low light, and GPS noise

Set the numeric pass thresholds after a baseline run on the official dataset. Do not invent accuracy claims before comparing to survey-grade references or known dimensions.

## Repository roadmap

```text
web/                 operator dashboard and 3D viewer (current static demo)
services/api/        auth, projects, job submission, signed asset URLs
services/worker/     frame, pose, dense, mesh, texture, validation tasks
packages/contracts/  JSON schemas: mission, artifact, model manifest, metrics
infra/               compose, CUDA-worker image, local object storage
datasets/            ignored raw data; versioned manifests and test fixtures only
docs/                methodology, API contract, validation protocol, demo script
```

### First sprint hand-offs

- Member 1 produces `frame_manifest.json` and selected, timestamped keyframes.
- Member 2 consumes the manifest and emits `trajectory.geojson`, `poses.json`, `sparse.ply`, and `geo_alignment.json`.
- Member 3 consumes poses/keyframes and emits `dense.ply` with per-point confidence.
- Member 4 emits `model.glb`, `model.las`, `coverage.geojson`, and an occlusion/confidence layer.
- Member 5 validates one immutable `result_manifest.json`; the UI reads this document only and never hard-codes result metrics.
- Member 6 rehearses a 3-minute proof: raw single-pass input → quality gate → geo trajectory → inspect model → measure known dimension → show accuracy/coverage/runtime report.

## Demo integrity rules

- Label sample/dashboard data as demo data until generated from the actual pipeline.
- Never fill occluded geometry without identifying it as inferred and lower confidence.
- Measurements must use the output CRS and display confidence/limitations near the result.
- Make every export traceable to source assets, pipeline versions, calibration, and validation run.
