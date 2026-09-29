def test_health_endpoint_returns_service_status(test_app) -> None:
    from conftest import request

    response = request(test_app, "GET", "/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "AeroTrace 3D"}
