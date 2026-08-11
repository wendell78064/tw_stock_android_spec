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
    result = {
        "as_of": meta.as_of.isoformat(),
        "received_at": meta.received_at.isoformat(),
        "data_status": meta.data_status.value,
        "source_code": meta.source_code,
        "source_revision": meta.source_revision,
    }
    policy = meta.provider_policy
    if policy is None and meta.source_code == "TWSE_LENDING":
        # Repository rows do not persist legal policy; resolve it from provider configuration.
        from app.adapters.twse.security_provider import TWSE_LENDING_POLICY

        policy = TWSE_LENDING_POLICY
    if policy:
        result.update(
            source_type=policy.source_type.value,
            source_capability=policy.source_capability.value,
            license_status=policy.license_status.value,
            automation_allowed=policy.automation_allowed,
            storage_allowed=policy.storage_allowed,
            redistribution_allowed=policy.redistribution_allowed,
        )
    return result


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
            values = {
                name: encode(getattr(row, name))
                for name in (
                    "trade_date",
                    "lending_sell",
                    "lending_return",
                    "lending_balance",
                    "lending_balance_change",
                )
            }
            values["lending_short_sell"] = encode(row.lending_short_sell)
            return values | metadata(row)

        return {
            "market": market.value,
            "security_code": security.code if security else None,
            "margin": [margin(row) for row in margins],
            "lending": [loan(row) for row in lending],
        }


class MarketOverviewService:
    def __init__(self, repository: MarketSpotRepository, derivatives_repository=None):
        self.repository = repository
        self.derivatives_repository = derivatives_repository

    async def overview(self) -> dict:
        indexes = await self.repository.indexes(None, None, None, 2)
        breadth = []
        institutional = []
        credit = []
        lending = []
        section_failed = False
        for market in MarketCode:
            try:
                breadth.extend((await self.repository.breadth(market, None, None))[-1:])
            except Exception:
                section_failed = True
            try:
                institutional.extend(
                    await InstitutionalService(self.repository).series(market, None, 1)
                )
            except Exception:
                section_failed = True
            try:
                section = await CreditTradingService(self.repository).series(market, None, 1)
                credit.extend(section["margin"])
                lending.extend(section["lending"])
            except Exception:
                section_failed = True
        statuses = [item.metadata.data_status for item in indexes + breadth]
        status = (
            DataStatus.FINAL
            if (
                statuses
                and all(item is DataStatus.FINAL for item in statuses)
                and not section_failed
            )
            else DataStatus.PARTIAL
        )
        futures = None
        institutional_futures = []
        derivatives_risk = {"put_call": None, "vix": None, "trader_concentration": []}
        if self.derivatives_repository:
            from app.services.derivatives import DerivativesRiskService, FuturesService

            try:
                futures = await FuturesService(
                    self.derivatives_repository, self.repository
                ).product_overview("TX")
                institutional_futures = await FuturesService(
                    self.derivatives_repository
                ).positions("TX", 1)
                put_call = await self.derivatives_repository.put_call("TXO", 1)
                concentration = await self.derivatives_repository.concentrations("TX", 1)
                vix = await DerivativesRiskService(self.derivatives_repository).volatility(1)
            except Exception:
                put_call, concentration, vix = [], [], []
                status = DataStatus.PARTIAL
            derivatives_risk = {
                "put_call": (
                    {
                        name: encode(getattr(put_call[-1], name))
                        for name in (
                            "trade_date",
                            "put_volume",
                            "call_volume",
                            "volume_put_call_ratio",
                            "put_open_interest",
                            "call_open_interest",
                            "oi_put_call_ratio",
                        )
                    }
                    if put_call
                    else None
                ),
                "vix": vix[-2] if len(vix) > 1 else None,
                "trader_concentration": [
                    {
                        name: encode(getattr(row, name))
                        for name in (
                            "contract_scope",
                            "side",
                            "top_n",
                            "open_interest",
                            "market_open_interest",
                            "concentration_ratio",
                        )
                    }
                    for row in concentration[-4:]
                ],
            }
            if not futures or not put_call or not vix:
                status = DataStatus.PARTIAL
        else:
            status = DataStatus.PARTIAL
        return {
            "data": {
                "indexes": [self._index(i) for i in indexes],
                "breadth": [self._breadth(i) for i in breadth],
                "institutional_spot": institutional,
                "credit": credit,
                "lending": lending,
                "futures": futures,
                "institutional_futures": institutional_futures,
                "derivatives_risk": derivatives_risk,
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
