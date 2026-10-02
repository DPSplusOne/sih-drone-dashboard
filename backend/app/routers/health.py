"""Service health routes."""

from fastapi import APIRouter


router = APIRouter(tags=["system"])


@router.get("/api/health")
async def health_check() -> dict[str, str]:
    """Return a lightweight liveness response without pipeline side effects."""

    return {"status": "ok", "service": "AeroTrace 3D"}
