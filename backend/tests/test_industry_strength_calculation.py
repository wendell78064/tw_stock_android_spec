from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.services.industry_strength_calculation import IndustryStrengthCalculationService


class ScalarQueueSession:
    def __init__(self, rows):
        self.rows = list(rows)
        self.committed = False

    def scalars(self, _statement):
        return ScalarResult(self.rows.pop(0))

    def commit(self):
        self.committed = True


class ScalarResult(list):
    def all(self):
        return list(self)

    def first(self):
        return self[0] if self else None


class UpsertSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []

    def scalars(self, _statement):
        return ScalarResult([] if self.existing is None else [self.existing])

    def add(self, row):
        self.added.append(row)


def strength_item(*, trade_date: date = date(2026, 9, 9)) -> dict:
    return {
        "taxonomy_id": uuid4(),
        "trade_date": trade_date,
        "window": 20,
        "algorithm_version": "twml-industry-strength-v1",
        "equal_weight_return": Decimal("0.0100"),
        "market_cap_weighted_return": None,
        "total_members": 1,
        "valid_members": 1,
        "coverage_ratio": Decimal("1.0000"),
        "advancers": 1,
        "decliners": 0,
        "unchanged": 0,
        "advance_ratio": Decimal("1.0000"),
        "above_ma20_pct": Decimal("1.0000"),
        "above_ma60_pct": Decimal("1.0000"),
        "foreign_net_amount": Decimal("0"),
        "investment_trust_net_amount": Decimal("0"),
        "dealer_net_amount": Decimal("0"),
        "margin_balance_change": Decimal("0"),
        "short_balance_change": Decimal("0"),
        "lending_balance_change": None,
        "turnover_amount": Decimal("1000"),
        "turnover_share": None,
        "turnover_momentum": Decimal("1.0"),
        "strength_score": Decimal("50"),
        "component_coverage": Decimal("1.0000"),
        "rank": 1,
        "data_status": "FINAL",
        "as_of": datetime(2026, 9, 10, tzinfo=UTC),
        "components": SimpleNamespace(
            momentum_score=Decimal("50"),
            breadth_score=Decimal("50"),
            technical_score=Decimal("50"),
            institutional_score=Decimal("50"),
            turnover_score=Decimal("50"),
        ),
    }


def test_industry_metrics_use_volume_shares_and_close_return_direction() -> None:
    security_id = uuid4()
    latest = SimpleNamespace(
        security_id=security_id,
        close=Decimal("110"),
        volume_shares=10,
    )
    base = SimpleNamespace(security_id=security_id, close=Decimal("100"))
    session = ScalarQueueSession([[latest], [base], [], [], []])
    service = IndustryStrengthCalculationService(session)

    result = service._aggregate_taxonomy_metrics(
        taxonomy_id=uuid4(),
        taxonomy_code="24",
        taxonomy_name="半導體業",
        taxonomy_type="OFFICIAL",
        sec_ids=[security_id],
        sec_codes={security_id: "1234"},
        latest_date=date(2026, 9, 9),
        base_date=date(2026, 9, 8),
        window=1,
        trading_days=[date(2026, 9, 9)],
    )

    assert result["equal_weight_return"] == Decimal("0.1000")
    assert (result["advancers"], result["decliners"], result["unchanged"]) == (1, 0, 0)
    assert result["turnover_amount"] == Decimal("1100")
    assert result["margin_balance_change"] == 0


def test_empty_taxonomy_is_truthful_idempotent_no_data() -> None:
    session = ScalarQueueSession([[], [], [], [], [], [], []])
    service = IndustryStrengthCalculationService(session)

    result = service.calculate_for_date(date(2026, 9, 9))

    assert result == {"inserted": 0, "updated": 0}
    assert session.committed


def test_strength_snapshot_insert_sets_utc_calculation_time_and_keeps_trade_date() -> None:
    session = UpsertSession()
    service = IndustryStrengthCalculationService(session)
    item = strength_item()

    assert service._upsert_snapshot(item, is_industry=True) == (1, 0)

    snapshot = session.added[0]
    assert snapshot.trade_date == date(2026, 9, 9)
    assert snapshot.calculated_at is not None
    assert snapshot.calculated_at.tzinfo is UTC


def test_strength_snapshot_recalculation_refreshes_calculation_time_without_duplicate() -> None:
    old_calculated_at = datetime(2026, 9, 9, tzinfo=UTC)
    existing = SimpleNamespace(
        trade_date=date(2026, 9, 9), calculated_at=old_calculated_at
    )
    session = UpsertSession(existing)
    service = IndustryStrengthCalculationService(session)
    item = strength_item()

    assert service._upsert_snapshot(item, is_industry=True) == (0, 1)

    assert session.added == []
    assert existing.calculated_at > old_calculated_at
    assert existing.calculated_at.tzinfo is UTC
    assert existing.trade_date == date(2026, 9, 9)


def test_many_strength_snapshot_inserts_all_receive_calculation_time() -> None:
    session = UpsertSession()
    service = IndustryStrengthCalculationService(session)

    for _ in range(60):
        assert service._upsert_snapshot(strength_item(), is_industry=True) == (1, 0)

    assert len(session.added) == 60
    assert all(row.calculated_at is not None for row in session.added)
