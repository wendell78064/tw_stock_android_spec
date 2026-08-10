from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.core.dependencies import readiness_checker
from app.main import app


def test_health_is_public_and_alive() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_ready_reports_dependencies() -> None:
    checker = AsyncMock()
    checker.check.return_value = {"postgres": "ok", "redis": "ok"}
    app.dependency_overrides[readiness_checker] = lambda: checker
    try:
        with TestClient(app) as client:
            response = client.get("/v1/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"postgres": "ok", "redis": "ok"}}
