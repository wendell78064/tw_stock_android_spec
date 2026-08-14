from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.errors import AppError
from app.repositories.models import (
    PortfolioModel,
    PortfolioTransactionModel,
    SecurityModel,
    SyncChangeModel,
    WatchlistItemModel,
    WatchlistModel,
)
from app.services.import_export import (
    ExportService,
    ImportService,
    ReportService,
    escape_formula,
    unescape_formula,
)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
ZERO = Decimal("0")


class FakeSession:
    def __init__(self):
        self.scalar_results = []
        self.objects = {}
        self.added = []
        self.sequence = 0

    async def scalar(self, statement):
        for col in getattr(statement, "selected_columns", ()):
            col_str = str(col).lower()
            if "sequence" in col_str or "max" in col_str or "coalesce" in col_str:
                return self.sequence
        if self.scalar_results:
            return self.scalar_results.pop(0)

        user_id = None
        target_id = None
        for crit in getattr(statement, "_where_criteria", ()):
            col_name = getattr(getattr(crit, "left", None), "name", None)
            val = getattr(getattr(crit, "right", None), "value", None)
            if col_name == "user_id":
                user_id = val
            elif col_name in ("portfolio_id", "id"):
                target_id = val

        entity = getattr(statement, "column_descriptions", [{}])[0].get("entity")
        if entity:
            for (kind, _), value in self.objects.items():
                if kind is entity:
                    if user_id is not None and getattr(value, "user_id", None) != user_id:
                        continue
                    if target_id is not None and getattr(value, "id", None) != target_id:
                        continue
                    return value
        return None

    async def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        user_id = None
        portfolio_id = None
        watchlist_id = None
        for crit in getattr(statement, "_where_criteria", ()):
            col_name = getattr(getattr(crit, "left", None), "name", None)
            val = getattr(getattr(crit, "right", None), "value", None)
            if col_name == "user_id":
                user_id = val
            elif col_name == "portfolio_id":
                portfolio_id = val
            elif col_name == "watchlist_id":
                watchlist_id = val

        values = [
            value
            for (kind, _), value in self.objects.items()
            if kind is entity
            and (user_id is None or getattr(value, "user_id", None) == user_id)
            and (portfolio_id is None or getattr(value, "portfolio_id", None) == portfolio_id)
            and (watchlist_id is None or getattr(value, "watchlist_id", None) == watchlist_id)
        ]
        return SimpleNamespace(all=lambda: values)

    async def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def add(self, value):
        self.added.append(value)
        if hasattr(value, "id"):
            self.objects[(type(value), value.id)] = value

    async def flush(self):
        for value in self.added:
            if isinstance(value, SyncChangeModel) and value.sequence is None:
                self.sequence += 1
                value.sequence = self.sequence

    async def commit(self):
        await self.flush()


def test_formula_injection_escaping():
    assert escape_formula("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert escape_formula("+123") == "'+123"
    assert escape_formula("-test") == "'-test"
    assert escape_formula("@macro") == "'@macro"
    assert escape_formula("Normal Text") == "Normal Text"
    assert unescape_formula("'=SUM(A1)") == "=SUM(A1)"
    assert unescape_formula("Normal") == "Normal"


@pytest.mark.asyncio
async def test_portfolio_transactions_export():
    session = FakeSession()
    user_id = uuid4()
    portfolio_id = uuid4()
    sec_id = uuid4()

    sec = SimpleNamespace(
        id=sec_id,
        market="TWSE",
        code="2330",
        name="TSMC",
        security_type="COMMON_STOCK",
        is_active=True,
    )
    pf = PortfolioModel(
        id=portfolio_id,
        user_id=user_id,
        name="=My Portfolio",  # formula injection attempt in portfolio name
        base_currency="TWD",
        is_default=True,
        version=1,
    )
    tx_id = uuid4()
    now_utc = datetime(2026, 8, 14, 1, 30, 0, tzinfo=UTC)
    tx = PortfolioTransactionModel(
        id=tx_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        security_id=sec_id,
        side="BUY",
        executed_at=now_utc,
        quantity_shares=1000,
        price=Decimal("950.50"),
        fee=Decimal("20.00"),
        lot_type="BOARD_LOT",
        version=1,
        created_at=now_utc,
        updated_at=now_utc,
    )

    session.objects[(SecurityModel, sec_id)] = sec
    session.objects[(PortfolioModel, portfolio_id)] = pf
    session.objects[(PortfolioTransactionModel, tx_id)] = tx

    service = ExportService(session)
    csv_bytes = await service.export_portfolio_transactions_csv(user_id, portfolio_id)

    # Validate UTF-8 BOM
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    content = csv_bytes.decode("utf-8-sig")
    lines = content.strip().split("\r\n")

    # Header check
    assert lines[0] == (
        "format_version,transaction_id,portfolio_name,market,code,side,"
        "trade_date,trade_time,shares,price,fee,lot_type"
    )
    row = lines[1].split(",")
    assert row[0] == "twml-portfolio-csv-v1"
    assert row[1] == str(tx_id)
    assert row[2] == "'=My Portfolio"
    assert row[3] == "TWSE"
    assert row[4] == "2330"
    assert row[5] == "BUY"
    assert row[6] == "2026-08-14"
    assert row[7] == "09:30:00"
    assert row[8] == "1000"
    assert row[9] == "950.500000" or row[9].startswith("950.5")
    assert row[10] == "20.000000" or row[10].startswith("20.0")
    assert row[11] == "BOARD_LOT"


@pytest.mark.asyncio
async def test_cross_user_export_blocked():
    session = FakeSession()
    user_a = uuid4()
    user_b = uuid4()
    portfolio_id = uuid4()

    pf = PortfolioModel(
        id=portfolio_id,
        user_id=user_a,
        name="User A Portfolio",
        base_currency="TWD",
        is_default=True,
    )
    session.objects[(PortfolioModel, portfolio_id)] = pf

    service = ExportService(session)
    with pytest.raises(AppError) as exc_info:
        await service.export_portfolio_transactions_csv(user_b, portfolio_id)
    assert exc_info.value.code == "PORTFOLIO_NOT_FOUND"


@pytest.mark.asyncio
async def test_watchlists_export():
    session = FakeSession()
    user_id = uuid4()
    group_id = uuid4()
    sec_id = uuid4()
    item_id = uuid4()

    sec = SimpleNamespace(
        id=sec_id, market="TWSE", code="2330", name="TSMC", is_active=True
    )
    group = WatchlistModel(
        id=group_id, user_id=user_id, name="Tech Leaders", sort_order=0, version=1
    )
    item = WatchlistItemModel(
        id=item_id,
        user_id=user_id,
        watchlist_id=group_id,
        security_id=sec_id,
        sort_order=0,
        note="@Core Holding",  # formula injection attempt
        target_price=Decimal("1100.00"),
        stop_price=Decimal("850.00"),
        add_price=Decimal("920.00"),
        version=1,
    )

    session.objects[(SecurityModel, sec_id)] = sec
    session.objects[(WatchlistModel, group_id)] = group
    session.objects[(WatchlistItemModel, item_id)] = item

    service = ExportService(session)
    csv_bytes = await service.export_watchlists_csv(user_id)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    content = csv_bytes.decode("utf-8-sig")
    lines = content.strip().split("\r\n")

    assert lines[0] == (
        "format_version,group_id,group_name,group_order,market,code,item_order,"
        "note,target_price,stop_price,add_price"
    )
    row = lines[1].split(",")
    assert row[0] == "twml-watchlist-csv-v1"
    assert row[1] == str(group_id)
    assert row[2] == "Tech Leaders"
    assert row[4] == "TWSE"
    assert row[5] == "2330"
    assert row[7] == "'@Core Holding"
    assert "1100" in row[8]


@pytest.mark.asyncio
async def test_portfolio_pdf_report_generation():
    session = FakeSession()
    user_id = uuid4()
    portfolio_id = uuid4()
    sec_id = uuid4()
    tx_id = uuid4()

    sec = SimpleNamespace(
        id=sec_id, market="TWSE", code="2330", name="TSMC", is_active=True
    )
    pf = PortfolioModel(
        id=portfolio_id, user_id=user_id, name="Growth Fund", base_currency="TWD", version=1
    )
    now_utc = datetime(2026, 8, 14, 1, 30, 0, tzinfo=UTC)
    tx = PortfolioTransactionModel(
        id=tx_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        security_id=sec_id,
        side="BUY",
        executed_at=now_utc,
        quantity_shares=1000,
        price=Decimal("900.00"),
        fee=Decimal("15.00"),
        lot_type="BOARD_LOT",
        version=1,
        created_at=now_utc,
        updated_at=now_utc,
    )

    session.objects[(SecurityModel, sec_id)] = sec
    session.objects[(PortfolioModel, portfolio_id)] = pf
    session.objects[(PortfolioTransactionModel, tx_id)] = tx

    service = ReportService(session)
    pdf_bytes = await service.generate_portfolio_pdf_report(user_id, portfolio_id)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 100


@pytest.mark.asyncio
async def test_portfolio_import_dry_run_and_apply():
    session = FakeSession()
    user_id = uuid4()
    portfolio_id = uuid4()
    sec_id = uuid4()

    sec = SimpleNamespace(
        id=sec_id, market="TWSE", code="2330", name="TSMC", is_active=True
    )
    pf = PortfolioModel(
        id=portfolio_id, user_id=user_id, name="Main Portfolio", base_currency="TWD", version=1
    )
    session.objects[(SecurityModel, sec_id)] = sec
    session.objects[(PortfolioModel, portfolio_id)] = pf

    csv_data = (
        "market,code,side,trade_date,trade_time,shares,price,fee,lot_type\n"
        "TWSE,2330,BUY,2026-08-10,09:30:00,1000,900.0,20.0,BOARD_LOT\n"
        "TWSE,2330,SELL,2026-08-12,10:00:00,500,950.0,15.0,BOARD_LOT\n"
    )

    service = ImportService(session)

    # 1. Dry Run / Preview
    preview = await service.preview_portfolio_csv(user_id, csv_data, portfolio_id)
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 2
    assert preview["invalid_rows"] == 0
    assert preview["duplicate_rows"] == 0
    assert len(preview["transactions"]) == 2
    token = preview["token"]

    # 2. Apply Confirmed Import
    result = await service.apply_portfolio_import(user_id, token, portfolio_id)
    assert result["status"] == "APPLIED"
    assert result["inserted_count"] == 2
    assert result["skipped_count"] == 0

    # 3. Verify Sync Change Log emitted
    sync_changes = [v for v in session.added if isinstance(v, SyncChangeModel)]
    assert len(sync_changes) == 2
    assert all(sc.entity_type == "PORTFOLIO_TRANSACTION" for sc in sync_changes)
    assert all(sc.sequence is not None for sc in sync_changes)


@pytest.mark.asyncio
async def test_portfolio_import_oversell_rejection():
    session = FakeSession()
    user_id = uuid4()
    portfolio_id = uuid4()
    sec_id = uuid4()

    sec = SimpleNamespace(
        id=sec_id, market="TWSE", code="2330", name="TSMC", is_active=True
    )
    pf = PortfolioModel(
        id=portfolio_id, user_id=user_id, name="Test PF", base_currency="TWD", version=1
    )
    session.objects[(SecurityModel, sec_id)] = sec
    session.objects[(PortfolioModel, portfolio_id)] = pf

    # Attempting to SELL before BUY (oversell)
    oversell_csv = (
        "market,code,side,trade_date,trade_time,shares,price,fee,lot_type\n"
        "TWSE,2330,SELL,2026-08-10,09:30:00,500,950.0,15.0,BOARD_LOT\n"
    )

    service = ImportService(session)
    preview = await service.preview_portfolio_csv(user_id, oversell_csv, portfolio_id)
    assert preview["invalid_rows"] > 0
    assert any(e["error_code"] == "OVERSELL" for e in preview["errors"])

    # Attempting to apply invalid preview must raise error
    with pytest.raises(AppError) as exc_info:
        await service.apply_portfolio_import(user_id, preview["token"], portfolio_id)
    assert exc_info.value.code == "IMPORT_HAS_ERRORS"


@pytest.mark.asyncio
async def test_watchlist_import_merge_and_replace():
    session = FakeSession()
    user_id = uuid4()
    sec_id = uuid4()

    sec = SimpleNamespace(
        id=sec_id, market="TWSE", code="2330", name="TSMC", is_active=True
    )
    session.objects[(SecurityModel, sec_id)] = sec

    wl_csv = (
        "group_name,market,code,note,target_price,stop_price,add_price\n"
        "Dividend Stars,TWSE,2330,High Yield,1000.0,800.0,900.0\n"
    )

    service = ImportService(session)

    # 1. Preview
    preview = await service.preview_watchlist_csv(user_id, wl_csv, merge_mode="MERGE")
    assert preview["total_rows"] == 1
    assert preview["valid_rows"] == 1
    assert preview["invalid_rows"] == 0
    assert len(preview["groups"]) == 1

    # 2. Apply MERGE
    result = await service.apply_watchlist_import(user_id, preview["token"], merge_mode="MERGE")
    assert result["status"] == "APPLIED"
    assert result["groups_count"] == 1
    assert result["items_count"] == 1

    # Verify Sync Changes
    wl_changes = [v for v in session.added if isinstance(v, SyncChangeModel)]
    assert len(wl_changes) == 2  # 1 group + 1 item
