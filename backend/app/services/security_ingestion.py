import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market_data import MarketDataProvider
from app.domain.security import SecurityRepository
from app.repositories.models import IngestionRunModel


class SecurityIngestionService:
    def __init__(self, session: AsyncSession, repository: SecurityRepository):
        self.session = session
        self.repository = repository

    async def synchronize(self, provider: MarketDataProvider) -> list[IngestionRunModel]:
        started_at = datetime.now(UTC)
        try:
            records = await provider.list_securities()
        except Exception as error:
            run = IngestionRunModel(
                id=uuid4(),
                provider=getattr(provider, "source_code", type(provider).__name__),
                dataset="SECURITY_MASTER",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                status="FAILED",
                fetched_count=0,
                inserted_count=0,
                updated_count=0,
                rejected_count=0,
                retry_count=0,
                error_message=str(error),
            )
            self.session.add(run)
            await self.session.commit()
            raise
        if not records:
            raise ValueError("provider returned no security records")
        results: list[IngestionRunModel] = []
        for market in sorted({record.market for record in records}, key=lambda item: item.value):
            market_records = [record for record in records if record.market is market]
            run = IngestionRunModel(
                id=uuid4(),
                provider=market_records[0].source_code if market_records else market.value,
                dataset="SECURITY_MASTER",
                started_at=datetime.now(UTC),
                status="RUNNING",
                fetched_count=len(market_records),
                inserted_count=0,
                updated_count=0,
                rejected_count=0,
                retry_count=0,
            )
            self.session.add(run)
            await self.session.flush()
            try:
                inserted, updated, inactive = await self.repository.synchronize(
                    market, market_records, run.id
                )
                run.inserted_count = inserted
                run.updated_count = updated + inactive
                run.checksum = self._checksum(market_records)
                run.status = "SUCCEEDED"
                run.finished_at = datetime.now(UTC)
                await self.session.commit()
            except Exception as error:
                await self.session.rollback()
                failed = IngestionRunModel(
                    id=run.id,
                    provider=run.provider,
                    dataset=run.dataset,
                    started_at=run.started_at,
                    finished_at=datetime.now(UTC),
                    status="FAILED",
                    fetched_count=len(market_records),
                    inserted_count=0,
                    updated_count=0,
                    rejected_count=len(market_records),
                    retry_count=0,
                    error_message=str(error),
                )
                self.session.add(failed)
                await self.session.commit()
                raise
            results.append(run)
        return results

    @staticmethod
    def _checksum(records) -> str:
        value = "|".join(sorted(f"{r.market.value}:{r.code}:{r.name}" for r in records))
        return hashlib.sha256(value.encode()).hexdigest()
