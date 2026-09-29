import asyncio

import httpx

from backend.app.main import app


def test_health_endpoint_returns_service_status() -> None:
    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.get("/api/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "AeroTrace 3D"}
