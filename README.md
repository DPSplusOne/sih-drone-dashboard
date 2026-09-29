# AeroTrace 3D

AeroTrace 3D is an SIH26158 project for converting a single-pass drone video, GPS coordinates, and flight metadata into a metrically scaled, georeferenced 3D reconstruction.

The current repository contains a responsive dashboard prototype for the operator workflow: mission input, frame-quality checks, pose and georeferencing progress, reconstruction status, model inspection, validation evidence, and artifact export.

## Current scope

The dashboard remains a static frontend prototype in Phase 1. A FastAPI health-service scaffold, local-development configuration, directory setup, structured logging, and tests are now available. Its displayed project data and reconstruction preview remain illustrative until later pipeline stages provide real artifacts and metrics.

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

## Frontend placement

`index.html`, `styles.css`, and `app.js` intentionally remain at the repository root in Phase 1. Moving them before API integration would create unnecessary path churn (including the current documentation link) without improving the visual experience. They will move together into `frontend/` when modular API, pipeline-state, and Three.js viewer code is introduced in a dedicated frontend-integration phase.
