import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market_spot import (
    InstitutionalRecord,
    LendingRecord,
    MarginRecord,
    MarketIndexRecord,
    MarketSpotProvider,
    MarketSpotRepository,
)
from app.repositories.models import IngestionRunModel

DATASETS = {
    "MARKET_INDEXES": "get_market_indexes",
    "MARKET_BREADTH": "get_market_breadth",
    "MARKET_INSTITUTIONAL": "get_market_institutional_spot",
    "SECURITY_INSTITUTIONAL": "get_security_institutional_spot",
    "MARKET_MARGIN": "get_market_margin_trading",
    "SECURITY_MARGIN": "get_security_margin_trading",
    "MARKET_LENDING": "get_market_securities_lending",
    "SECURITY_LENDING": "get_security_securities_lending",
}


def validate_record(record: object) -> str | None:
    if isinstance(record, MarketIndexRecord) and all(
        value is not None for value in (record.open, record.high, record.low, record.close)
    ):
        assert (
            record.open is not None
            and record.high is not None
            and record.low is not None
            and record.close is not None
        )
        if (
            record.high < max(record.open, record.close)
            or record.low > min(record.open, record.close)
            or record.high < record.low
        ):
            return "INVALID_OHLC"
    if (
        isinstance(record, InstitutionalRecord)
        and record.buy is not None
        and record.sell is not None
        and record.net is not None
    ):
        if abs(Decimal(record.net) - (Decimal(record.buy) - Decimal(record.sell))) > Decimal(
            "0.01"
        ):
            return "INVALID_NET"
    if isinstance(record, MarginRecord):
        values = (
            record.margin_buy,
            record.margin_sell,
            record.margin_cash_repayment,
            record.margin_balance,
            record.short_sell,
            record.short_cover,
            record.short_stock_repayment,
            record.short_balance,
        )
        if any(value is not None and value < 0 for value in values):
            return "NEGATIVE_MARGIN"
    if isinstance(record, LendingRecord) and any(
        value is not None and value < 0
        for value in (record.lending_sell, record.lending_return, record.lending_balance)
    ):
        return "NEGATIVE_LENDING"
    for name in ("advancers", "decliners", "unchanged", "limit_up", "limit_down"):
        if (
            hasattr(record, name)
            and getattr(record, name) is not None
            and getattr(record, name) < 0
        ):
            return "NEGATIVE_BREADTH"
    return None


class MarketSpotIngestionService:
    def __init__(self, session: AsyncSession, repository: MarketSpotRepository):
        self.session, self.repository = session, repository

    async def synchronize_dataset(
        self, provider: MarketSpotProvider, dataset: str, trade_date: date, retry_count: int = 0
    ) -> IngestionRunModel:
        started = datetime.now(UTC)
        run = IngestionRunModel(
            id=uuid4(),
            provider=provider.source_code,
            dataset=dataset,
            started_at=started,
            status="RUNNING",
            fetched_count=0,
            inserted_count=0,
            updated_count=0,
            rejected_count=0,
            retry_count=retry_count,
        )
        self.session.add(run)
        await self.session.flush()
        try:
            records = await getattr(provider, DATASETS[dataset])(trade_date)
            run.fetched_count = len(records)
            unique = []
            seen = set()
            for record in records:
                identity = repr(record)[: repr(record).find("metadata=")]
                if identity in seen or validate_record(record):
                    run.rejected_count += 1
                else:
                    seen.add(identity)
                    unique.append(record)
            run.inserted_count, run.updated_count = await self.repository.synchronize(
                dataset, unique, run.id
            )
            run.checksum = hashlib.sha256("|".join(sorted(seen)).encode()).hexdigest()
            run.status = "PARTIAL" if run.rejected_count else "SUCCEEDED"
            run.finished_at = datetime.now(UTC)
            await self.session.commit()
            return run
        except Exception as error:
            await self.session.rollback()
            failed = IngestionRunModel(
                id=run.id,
                provider=run.provider,
                dataset=dataset,
                started_at=started,
                finished_at=datetime.now(UTC),
                status="FAILED",
                fetched_count=run.fetched_count,
                inserted_count=0,
                updated_count=0,
                rejected_count=run.fetched_count,
                retry_count=retry_count,
                error_message=str(error),
            )
            self.session.add(failed)
            await self.session.commit()
            raise
