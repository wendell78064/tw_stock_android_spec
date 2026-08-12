from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.industry_strength import (
    ALGORITHM_VERSION,
    StrengthComponents,
    TaxonomyLeader,
    TaxonomyStrengthDetail,
    TaxonomyStrengthSnapshot,
)
from app.domain.market_data import DataStatus
from app.domain.security import MarketCode
from app.main import app
from app.services.industry_strength_scoring import IndustryStrengthScoringService


def test_strength_scoring_service_deterministic():
    service = IndustryStrengthScoringService()

    raw_items = [
        ("id1", Decimal("10.5")),
        ("id2", Decimal("5.0")),
        ("id3", Decimal("20.0")),
    ]
    percentiles = service.calculate_percentile_scores(raw_items)

    assert percentiles["id2"] == Decimal("0.00")
    assert percentiles["id1"] == Decimal("50.00")
    assert percentiles["id3"] == Decimal("100.00")


def test_strength_scoring_missing_component_reweighting():
    service = IndustryStrengthScoringService()

    group_data = [
        {
            "taxonomy_id": "ind1",
            "taxonomy_code": "24",
            "equal_weight_return": Decimal("0.05"),
            "advance_ratio": Decimal("0.80"),
            "above_ma20_pct": Decimal("0.90"),
            "above_ma60_pct": Decimal("0.70"),
            "foreign_net_amount": Decimal("1000000"),
            "turnover_momentum": None,  # Missing component
        },
        {
            "taxonomy_id": "ind2",
            "taxonomy_code": "25",
            "equal_weight_return": Decimal("0.02"),
            "advance_ratio": Decimal("0.40"),
            "above_ma20_pct": Decimal("0.50"),
            "above_ma60_pct": Decimal("0.50"),
            "foreign_net_amount": Decimal("200000"),
            "turnover_momentum": None,  # Missing component
        },
    ]

    scored = service.score_group(group_data)

    assert len(scored) == 2
    # Available weights = 30 + 25 + 20 + 15 = 90% = 0.90
    assert scored[0]["component_coverage"] == Decimal("0.9000")
    assert scored[0]["strength_score"] is not None
    assert Decimal("0") <= scored[0]["strength_score"] <= Decimal("100")
    assert scored[0]["algorithm_version"] == ALGORITHM_VERSION
    assert scored[0]["rank"] == 1
    assert scored[1]["rank"] == 2


def test_strength_scoring_coverage_below_threshold():
    service = IndustryStrengthScoringService()

    # Only Momentum (30%) is available -> coverage = 0.30 < 0.60 threshold
    group_data = [
        {
            "taxonomy_id": "ind1",
            "taxonomy_code": "24",
            "equal_weight_return": Decimal("0.05"),
            "advance_ratio": None,
            "above_ma20_pct": None,
            "above_ma60_pct": None,
            "foreign_net_amount": None,
            "turnover_momentum": None,
        }
    ]

    scored = service.score_group(group_data)
    assert len(scored) == 1
    assert scored[0]["component_coverage"] == Decimal("0.3000")
    assert scored[0]["strength_score"] is None
    assert scored[0]["rank"] is None


class InMemoryStrengthRepository:
    def __init__(self):
        self.snapshots = []

    async def get_industry_strengths(self, window: int = 20, trade_date: date | None = None, sort_by: str = "strength"):
        return [s for s in self.snapshots if s.taxonomy_type == "OFFICIAL" and s.window == window]

    async def get_theme_strengths(self, window: int = 20, trade_date: date | None = None, sort_by: str = "strength"):
        return [s for s in self.snapshots if s.taxonomy_type == "CUSTOM" and s.window == window]

    async def get_taxonomy_strength_detail(self, taxonomy_id, is_industry: bool, window: int = 20, trade_date: date | None = None):
        match = next((s for s in self.snapshots if s.taxonomy_id == taxonomy_id and s.window == window), None)
        if not match:
            return None

        leader = TaxonomyLeader(
            security_id=uuid4(),
            code="2330",
            name="台積電",
            market=MarketCode.TWSE,
            return_pct=Decimal("5.25"),
            latest_close=Decimal("1000.0"),
            foreign_net=Decimal("5000000"),
            data_status=DataStatus.FINAL,
        )
        laggard = TaxonomyLeader(
            security_id=uuid4(),
            code="2303",
            name="聯電",
            market=MarketCode.TWSE,
            return_pct=Decimal("-1.20"),
            latest_close=Decimal("50.0"),
            foreign_net=Decimal("-1000000"),
            data_status=DataStatus.FINAL,
        )

        return TaxonomyStrengthDetail(snapshot=match, leaders=[leader], laggards=[laggard])

    async def get_taxonomy_strength_history(self, taxonomy_id, is_industry: bool, window: int = 20, limit: int = 60):
        return [s for s in self.snapshots if s.taxonomy_id == taxonomy_id and s.window == window][:limit]


@pytest.fixture
def mock_strength_repo(app_client):
    repo = InMemoryStrengthRepository()
    ind_id = uuid4()
    snap = TaxonomyStrengthSnapshot(
        id=uuid4(),
        taxonomy_id=ind_id,
        taxonomy_code="24",
        taxonomy_name="半導體",
        taxonomy_type="OFFICIAL",
        trade_date=date(2026, 8, 11),
        window=20,
        equal_weight_return=Decimal("0.0450"),
        market_cap_weighted_return=None,
        total_members=10,
        valid_members=10,
        coverage_ratio=Decimal("1.0000"),
        advancers=7,
        decliners=2,
        unchanged=1,
        advance_ratio=Decimal("0.7000"),
        above_ma20_pct=Decimal("0.8000"),
        above_ma60_pct=Decimal("0.6000"),
        foreign_net_amount=Decimal("5000000"),
        investment_trust_net_amount=Decimal("1000000"),
        dealer_net_amount=Decimal("500000"),
        margin_balance_change=Decimal("200000"),
        short_balance_change=Decimal("10000"),
        lending_balance_change=None,
        turnover_amount=Decimal("5000000000"),
        turnover_share=None,
        turnover_momentum=Decimal("1.2"),
        components=StrengthComponents(
            momentum_score=Decimal("85.00"),
            breadth_score=Decimal("75.00"),
            technical_score=Decimal("70.00"),
            institutional_score=Decimal("80.00"),
            turnover_score=Decimal("60.00"),
        ),
        strength_score=Decimal("78.50"),
        component_coverage=Decimal("1.0000"),
        rank=1,
        algorithm_version=ALGORITHM_VERSION,
        data_status=DataStatus.FINAL,
        as_of=datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc),
    )
    repo.snapshots.append(snap)

    from app.core.dependencies import industry_strength_repository
    app.dependency_overrides[industry_strength_repository] = lambda: repo
    yield repo, ind_id
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_api_list_industry_strengths(client, mock_strength_repo):
    repo, ind_id = mock_strength_repo
    response = client.get("/v1/industries/strength?window=20")
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    assert len(json_data["data"]) == 1
    item = json_data["data"][0]
    assert item["taxonomy_code"] == "24"
    assert item["strength_score"] == "78.50"
    assert item["rank"] == 1


def test_api_get_industry_strength_detail(client, mock_strength_repo):
    repo, ind_id = mock_strength_repo
    response = client.get(f"/v1/industries/{ind_id}/strength?window=20")
    assert response.status_code == 200
    json_data = response.json()["data"]
    assert json_data["snapshot"]["taxonomy_name"] == "半導體"
    assert len(json_data["leaders"]) == 1
    assert json_data["leaders"][0]["code"] == "2330"
    assert len(json_data["laggards"]) == 1
    assert json_data["laggards"][0]["code"] == "2303"


def test_api_get_industry_strength_history(client, mock_strength_repo):
    repo, ind_id = mock_strength_repo
    response = client.get(f"/v1/industries/{ind_id}/strength/history?window=20&limit=60")
    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["data"]) == 1
    assert json_data["data"][0]["algorithm_version"] == ALGORITHM_VERSION
