from datetime import date
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
