import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.derivatives import (
    DerivativesDataProvider,
    DerivativesRepository,
    FuturesDailyPrice,
    InstitutionFuturesPosition,
    OptionPutCallRatio,
    OptionStrikeOpenInterest,
    VolatilityIndex,
)
from app.repositories.models import IngestionRunModel

DERIVATIVE_DATASETS = {
    "FUTURES_PRODUCTS": "get_futures_products",
    "FUTURES_CONTRACTS": "get_futures_contracts",
    "FUTURES_DAILY": "get_futures_daily",
    "FUTURES_INSTITUTIONAL": "get_futures_institutional_positions",
    "TRADER_CONCENTRATION": "get_trader_concentration",
    "OPTION_PUT_CALL": "get_put_call_ratio",
    "OPTION_STRIKE_OI": "get_option_open_interest_by_strike",
    "VOLATILITY_INDEX": "get_volatility_index",
}


def derivative_error(row: object) -> str | None:
    if isinstance(row, FuturesDailyPrice):
        if all(x is not None for x in (row.open, row.high, row.low, row.close)):
            if (
                row.high < max(row.open, row.close)
                or row.low > min(row.open, row.close)
                or row.high < row.low
            ):
                return "INVALID_OHLC"
        if any(x is not None and x < 0 for x in (row.volume, row.open_interest)):
            return "NEGATIVE_COUNT"
    if isinstance(row, InstitutionFuturesPosition):
        if (
            row.long_oi is not None
            and row.short_oi is not None
            and row.net_oi != row.long_oi - row.short_oi
        ):
            return "INVALID_NET_OI"
        if (
            row.long_volume is not None
            and row.short_volume is not None
            and row.net_volume != row.long_volume - row.short_volume
        ):
            return "INVALID_NET_VOLUME"
    if isinstance(row, OptionPutCallRatio):
        if row.call_volume and row.volume_put_call_ratio is not None:
            expected = Decimal(row.put_volume) / Decimal(row.call_volume) * 100
            if abs(expected - row.volume_put_call_ratio) > Decimal("0.02"):
                return "INVALID_VOLUME_RATIO"
        if row.call_open_interest and row.oi_put_call_ratio is not None:
            expected = Decimal(row.put_open_interest) / Decimal(row.call_open_interest) * 100
            if abs(expected - row.oi_put_call_ratio) > Decimal("0.02"):
                return "INVALID_OI_RATIO"
    if isinstance(row, OptionStrikeOpenInterest) and (
        row.strike <= 0 or (row.open_interest is not None and row.open_interest < 0)
    ):
        return "INVALID_OPTION_OI"
    if isinstance(row, VolatilityIndex) and any(
        x is not None and x < 0 for x in (row.open, row.high, row.low, row.close)
    ):
        return "NEGATIVE_VIX"
    return None


class DerivativesIngestionService:
    def __init__(self, session: AsyncSession, repository: DerivativesRepository):
        self.session, self.repository = session, repository

    async def synchronize_dataset(
        self, provider: DerivativesDataProvider, dataset: str, target: date, retry_count: int = 0
    ):
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
            method = getattr(provider, DERIVATIVE_DATASETS[dataset])
            records = await method() if dataset == "FUTURES_PRODUCTS" else await method(target)
            run.fetched_count = len(records)
            accepted = []
            identities = set()
            for row in records:
                identity = repr(row).split("metadata=", 1)[0]
                if identity in identities or derivative_error(row):
                    run.rejected_count += 1
                else:
                    identities.add(identity)
                    accepted.append(row)
            run.inserted_count, run.updated_count = await self.repository.synchronize(
                dataset, accepted, run.id
            )
            run.checksum = hashlib.sha256("|".join(sorted(identities)).encode()).hexdigest()
            run.status = "PARTIAL" if run.rejected_count or not records else "SUCCEEDED"
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
