from datetime import date
from decimal import Decimal

from app.domain.market_data import DataStatus
from app.domain.market_spot import InstitutionType, MarketSpotRepository
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode

WINDOWS = {1, 5, 10, 20, 60}


def encode(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def metadata(record) -> dict:
    meta = record.metadata
    return {
        "as_of": meta.as_of.isoformat(),
        "received_at": meta.received_at.isoformat(),
        "data_status": meta.data_status.value,
        "source_code": meta.source_code,
        "source_revision": meta.source_revision,
    }


class InstitutionalService:
    def __init__(self, repository: MarketSpotRepository):
        self.repository = repository

    async def series(
        self,
        market: MarketCode,
        security: SecurityKey | None,
        window: int,
        start: date | None = None,
        end: date | None = None,
        institution: InstitutionType | None = None,
    ) -> list[dict]:
        if window not in WINDOWS:
            raise ValueError("window must be one of 1,5,10,20,60")
        rows = await self.repository.institutional(market, security, start, end, institution)
        dates = sorted({row.trade_date for row in rows})[-window:]
        selected = [row for row in rows if row.trade_date in dates]
        cumulative: dict[tuple, Decimal] = {}
        streak: dict[tuple, tuple[int, int]] = {}
        result = []
        for row in selected:
            key = (row.institution_type, row.dealer_subtype)
            net = Decimal(row.net) if row.net is not None else None
            if net is not None:
                cumulative[key] = cumulative.get(key, Decimal(0)) + net
                direction = 1 if net > 0 else -1 if net < 0 else 0
                previous, count = streak.get(key, (0, 0))
                streak[key] = (direction, count + 1 if direction == previous else 1)
            result.append(
                {
                    "market": market.value,
                    "security_code": security.code if security else None,
                    "trade_date": row.trade_date.isoformat(),
                    "institution_type": row.institution_type.value,
                    "dealer_subtype": row.dealer_subtype.value if row.dealer_subtype else None,
                    "buy": encode(row.buy),
                    "sell": encode(row.sell),
                    "net": encode(row.net),
                    "cumulative_net": encode(cumulative.get(key)),
                    "consecutive_direction_days": streak.get(key, (0, 0))[1],
                    **metadata(row),
                }
            )
        return result


class CreditTradingService:
    def __init__(self, repository: MarketSpotRepository):
        self.repository = repository

    async def series(
        self,
        market: MarketCode,
        security: SecurityKey | None,
        window: int = 60,
        start: date | None = None,
        end: date | None = None,
    ) -> dict:
        if window not in WINDOWS:
            raise ValueError("window must be one of 1,5,10,20,60")
        margins = (await self.repository.margins(market, security, start, end))[-window:]
        lending = (await self.repository.lending(market, security, start, end))[-window:]

        def margin(row):
            return {
                name: encode(getattr(row, name))
                for name in (
                    "trade_date",
                    "margin_buy",
                    "margin_sell",
                    "margin_cash_repayment",
                    "margin_balance",
                    "margin_balance_change",
                    "short_sell",
                    "short_cover",
                    "short_stock_repayment",
                    "short_balance",
                    "short_balance_change",
                    "short_margin_ratio",
                    "margin_utilization",
                    "short_utilization",
                )
            } | metadata(row)

        def loan(row):
            return {
                name: encode(getattr(row, name))
                for name in (
                    "trade_date",
                    "lending_sell",
                    "lending_return",
                    "lending_balance",
                    "lending_balance_change",
                )
            } | metadata(row)

        return {
            "market": market.value,
            "security_code": security.code if security else None,
            "margin": [margin(row) for row in margins],
            "lending": [loan(row) for row in lending],
        }


class MarketOverviewService:
    def __init__(self, repository: MarketSpotRepository):
        self.repository = repository

    async def overview(self) -> dict:
        indexes = await self.repository.indexes(None, None, None, 2)
        breadth = []
        institutional = []
        credit = []
        lending = []
        for market in MarketCode:
            breadth.extend((await self.repository.breadth(market, None, None))[-1:])
            institutional.extend(
                await InstitutionalService(self.repository).series(market, None, 1)
            )
            section = await CreditTradingService(self.repository).series(market, None, 1)
            credit.extend(section["margin"])
            lending.extend(section["lending"])
        statuses = [item.metadata.data_status for item in indexes + breadth]
        status = (
            DataStatus.FINAL
            if statuses and all(item is DataStatus.FINAL for item in statuses)
            else DataStatus.PARTIAL
        )
        return {
            "data": {
                "indexes": [self._index(i) for i in indexes],
                "breadth": [self._breadth(i) for i in breadth],
                "institutional_spot": institutional,
                "credit": credit,
                "lending": lending,
            },
            "meta": {
                "data_status": status.value,
                "as_of": max(
                    (i.metadata.as_of for i in indexes + breadth), default=None
                ).isoformat()
                if indexes or breadth
                else None,
                "source": "MARKET_SPOT_COMPOSITE",
            },
        }

    @staticmethod
    def _index(row):
        return {
            name: encode(getattr(row, name))
            for name in (
                "code",
                "name",
                "market",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "change",
                "change_percent",
                "turnover_amount",
                "volume",
            )
        } | metadata(row)

    @staticmethod
    def _breadth(row):
        return {
            name: encode(getattr(row, name))
            for name in (
                "market",
                "trade_date",
                "advancers",
                "decliners",
                "unchanged",
                "limit_up",
                "limit_down",
                "total_traded",
                "turnover_amount",
            )
        } | metadata(row)
