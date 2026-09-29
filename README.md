# AeroTrace 3D

AeroTrace 3D is an SIH26158 project for converting a single-pass drone video, GPS coordinates, and flight metadata into a metrically scaled, georeferenced 3D reconstruction.

The current repository contains a responsive dashboard prototype for the operator workflow: mission input, frame-quality checks, pose and georeferencing progress, reconstruction status, model inspection, validation evidence, and artifact export.

## Current scope

The dashboard is presently a static frontend prototype. Its displayed project data and reconstruction preview are illustrative only; a FastAPI, COLMAP/PyCOLMAP, Open3D, and Three.js implementation is planned but not yet scaffolded.

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
