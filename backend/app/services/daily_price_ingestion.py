import hashlib
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.calendar import TradingCalendar
from app.domain.market_data import MarketDataProvider
from app.domain.pricing import (
    DailyPriceRecord,
    PriceBasis,
    PriceRepository,
    SecurityKey,
    TechnicalSnapshot,
)
from app.repositories.models import IngestionRunModel
from app.services.candle_aggregation import CandleAggregationService
from app.services.technical_indicators import ALGORITHM_VERSION, TechnicalIndicatorService


def validate_price(record: DailyPriceRecord) -> str | None:
    if not record.has_trade:
        return None
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
    if record.volume_shares is not None and record.volume_shares < 0:
        return "NEGATIVE_VOLUME"
    return None


def is_expected_non_stock(code: str) -> bool:
    # 1. Warrants / Structured certificates (length >= 6)
    if len(code) >= 6:
        return True
    # 2. ETFs / ETNs / REITs (starts with 00, 01, 02, 03, 08)
    if code.startswith(("00", "01", "02", "03", "08")):
        return True
    # 3. TDRs (Taiwan Depositary Receipts, starts with 91)
    if code.startswith("91"):
        return True
    # 4. Preferred stocks / CBs (length 5)
    if len(code) == 5:
        return True
    return False


class DailyPriceIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        repository: PriceRepository,
        calendar: TradingCalendar | None = None,
    ):
        self.session, self.repository = session, repository
        self.calendar = calendar

    async def synchronize(
        self,
        provider: MarketDataProvider,
        *,
        trade_date: date | None = None,
        security: SecurityKey | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        retry_count: int = 0,
    ) -> IngestionRunModel:
        started = datetime.now(UTC)
        run = IngestionRunModel(
            id=uuid4(),
            provider=getattr(provider, "source_code", type(provider).__name__),
            dataset="DAILY_PRICES",
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
            records = await provider.get_daily_prices(trade_date, security, start_date, end_date)
            run.fetched_count = len(records)
            unique: dict[tuple[SecurityKey, date], DailyPriceRecord] = {}
            rejected = 0
            for record in records:
                key = (record.security, record.trade_date)
                if key in unique:
                    rejected += 1
                    continue
                if validate_price(record):
                    rejected += 1
                    continue
                if (
                    self.calendar is not None
                    and not self.calendar.is_trading_day(record.trade_date)
                ):
                    rejected += 1
                    continue
                unique[key] = record

            # Filter out expected non-stock instruments (ETFs, warrants, preferred) before DB synchronization
            accepted_records: list[DailyPriceRecord] = []
            for record in unique.values():
                code = record.security.code
                if security is None and is_expected_non_stock(code):
                    continue
                accepted_records.append(record)

            grouped: dict[SecurityKey, list[DailyPriceRecord]] = {}
            for record in accepted_records:
                grouped.setdefault(record.security, []).append(record)

            inserted = updated = failed = 0
            for _, group in grouped.items():
                try:
                    added, changed = await self.repository.synchronize(group, run.id)
                    inserted += added
                    updated += changed
                except LookupError:
                    # Legitimate common stock code missing from Security Master -> TRUE REJECTION
                    failed += len(group)

            run.inserted_count, run.updated_count = inserted, updated
            run.rejected_count = rejected + failed
            run.checksum = self._checksum(accepted_records)
            run.status = "PARTIAL" if run.rejected_count else "SUCCEEDED"
            run.finished_at = datetime.now(UTC)
            await self.session.commit()
            return run
        except Exception as error:
            await self.session.rollback()
            failed_run = IngestionRunModel(
                id=run.id,
                provider=run.provider,
                dataset=run.dataset,
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
            self.session.add(failed_run)
            await self.session.commit()
            raise

    @staticmethod
    def _checksum(records: list[DailyPriceRecord]) -> str:
        text = "|".join(
            sorted(
                f"{r.security.market}:{r.security.code}:{r.trade_date}:{r.close}:{r.source_revision}"
                for r in records
            )
        )
        return hashlib.sha256(text.encode()).hexdigest()


class TechnicalCalculationService:
    def __init__(self, repository: PriceRepository):
        self.repository = repository
        self.indicators = TechnicalIndicatorService()
        self.aggregation = CandleAggregationService()

    async def recalculate(self, security: SecurityKey, basis: PriceBasis) -> int:
        records = await self.repository.list_prices(security, None, None)
        from app.domain.pricing import CandleInterval

        candles = self.aggregation.aggregate(records, CandleInterval.DAY, basis)
        if not candles:
            await self.repository.replace_technicals(security, basis, [])
            return 0
        series = self.indicators.calculate(candles)
        record_by_date = {item.trade_date: item for item in records}
        snapshots = [
            TechnicalSnapshot(
                security,
                candle.trade_date,
                basis,
                values,
                ALGORITHM_VERSION,
                record_by_date[candle.trade_date].as_of,
                record_by_date[candle.trade_date].received_at,
                record_by_date[candle.trade_date].data_status,
            )
            for candle, values in zip(candles, series.values, strict=True)
        ]
        await self.repository.replace_technicals(security, basis, snapshots)
        return len(snapshots)
