from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

from app.core.dependencies import comparison_service
from app.domain.comparison import ComparisonSignalConfig
from app.main import app
from app.services.comparison import ComparisonService


def _make_comparison_service():
    """Return a ComparisonService with a mock session for validation-only tests."""
    mock_session = AsyncMock()
    return ComparisonService(mock_session)


@pytest.fixture
def app_client():
    client = TestClient(app)
    app.dependency_overrides[comparison_service] = _make_comparison_service
    yield app, client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_comparison_selection_validation(app_client):
    app, client = app_client

    # Less than 2 targets → 400
    res_less = client.post(
        "/v1/comparisons/run",
        json={"targets": [{"code": "2330", "market": "TWSE"}]},
    )
    assert res_less.status_code == 400

    # Duplicate targets → 400
    res_dup = client.post(
        "/v1/comparisons/run",
        json={
            "targets": [
                {"code": "2330", "market": "TWSE"},
                {"code": "2330", "market": "TWSE"},
            ]
        },
    )
    assert res_dup.status_code == 400

    # More than 5 targets → 400
    res_more = client.post(
        "/v1/comparisons/run",
        json={
            "targets": [
                {"code": "2330", "market": "TWSE"},
                {"code": "2317", "market": "TWSE"},
                {"code": "2454", "market": "TWSE"},
                {"code": "2308", "market": "TWSE"},
                {"code": "2382", "market": "TWSE"},
                {"code": "2303", "market": "TWSE"},
            ]
        },
    )
    assert res_more.status_code == 400


def test_signal_config_deterministic_thresholds():
    cfg = ComparisonSignalConfig()
    assert cfg.return_diff_pct_points_threshold == Decimal("5.0")
    assert cfg.rsi_diff_threshold == Decimal("15.0")
