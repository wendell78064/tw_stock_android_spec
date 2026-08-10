from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.domain.derivatives import DerivativesRepository, OptionType, RollMethod
from app.domain.market_spot import MarketSpotRepository


def encode(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def metadata(row):
    m = row.metadata
    return {
        "as_of": m.as_of.isoformat(),
        "received_at": m.received_at.isoformat(),
        "data_status": m.data_status.value,
        "source_code": m.source_code,
        "source_revision": m.source_revision,
    }


class ContinuousFuturesService:
    algorithm_version = "twml-continuous-v1"

    def build(self, rows, method: RollMethod):
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.trade_date].append(row)
        result = []
        previous = None
        for trade_date in sorted(grouped):
            candidates = grouped[trade_date]
            if method is RollMethod.VOLUME:
                selected = max(candidates, key=lambda x: (x.volume or -1, x.contract_month))
            elif method is RollMethod.OPEN_INTEREST:
                selected = max(candidates, key=lambda x: (x.open_interest or -1, x.contract_month))
            else:
                selected = min(candidates, key=lambda x: x.contract_month)
            rolled = previous is not None and previous != selected.contract_code
            result.append(
                {
                    "trade_date": trade_date.isoformat(),
                    "open": encode(selected.open),
                    "high": encode(selected.high),
                    "low": encode(selected.low),
                    "close": encode(selected.close),
                    "volume": selected.volume,
                    "open_interest": selected.open_interest,
                    "roll_method": method.value,
                    "source_contract": selected.contract_code,
                    "roll_date": trade_date.isoformat() if rolled else None,
                    "adjustment_method": "NONE",
                    "algorithm_version": self.algorithm_version,
                    **metadata(selected),
                }
            )
            previous = selected.contract_code
        return result


class OptionMaxPainService:
    algorithm_version = "twml-max-pain-v1"

    def calculate(self, rows):
        valid = [r for r in rows if r.open_interest is not None]
        if not valid:
            return {
                "data_status": "UNAVAILABLE",
                "derived": True,
                "algorithm_version": self.algorithm_version,
                "ties": [],
            }
        candidates = sorted({r.strike for r in valid})
        payouts = {}
        for candidate in candidates:
            total = Decimal(0)
            for row in valid:
                intrinsic = (
                    max(candidate - row.strike, Decimal(0))
                    if row.option_type is OptionType.CALL
                    else max(row.strike - candidate, Decimal(0))
                )
                total += intrinsic * row.open_interest
            payouts[candidate] = total
        minimum = min(payouts.values())
        ties = [strike for strike, payout in payouts.items() if payout == minimum]
        first = valid[0]
        return {
            "trade_date": first.trade_date.isoformat(),
            "expiry": first.expiry,
            "max_pain": encode(ties[0]) if len(ties) == 1 else None,
            "ties": [encode(x) for x in ties],
            "total_intrinsic_payout": encode(minimum),
            "algorithm_version": self.algorithm_version,
            "derived": True,
            "data_status": first.metadata.data_status.value,
            **metadata(first),
        }


class FuturesService:
    def __init__(
        self,
        repository: DerivativesRepository,
        market_repository: MarketSpotRepository | None = None,
    ):
        self.repository, self.market_repository = repository, market_repository

    async def product_overview(self, product_code: str):
        products = await self.repository.products(product_code)
        if not products:
            return None
        contracts = [c for c in await self.repository.contracts(product_code) if c.is_active]
        latest = await self.repository.daily(product_code, None, 20)
        if not latest:
            return {
                "product": self._product(products[0]),
                "near": None,
                "next": None,
                "data_status": "UNAVAILABLE",
            }
        latest_date = max(x.trade_date for x in latest)
        active_codes = [c.contract_code for c in sorted(contracts, key=lambda c: c.contract_month)]
        session_points = [
            x for x in latest if x.trade_date == latest_date and x.contract_code in active_codes
        ]
        by_contract = {}
        for point in session_points:
            current = by_contract.get(point.contract_code)
            if current is None or (
                point.session_type.value == "REGULAR" and current.session_type.value != "REGULAR"
            ):
                by_contract[point.contract_code] = point
        points = sorted(by_contract.values(), key=lambda x: x.contract_month)
        spot = None
        if product_code == "TX" and self.market_repository:
            indexes = await self.market_repository.indexes("TAIEX", latest_date, latest_date, 1)
            spot = indexes[-1].close if indexes else None
        result = {
            "product": self._product(products[0]),
            "near": self._daily(points[0], spot) if points else None,
            "next": self._daily(points[1], spot) if len(points) > 1 else None,
            "data_status": points[0].metadata.data_status.value if points else "UNAVAILABLE",
        }
        return result

    @staticmethod
    def _product(row):
        return {
            "code": row.code,
            "name": row.name,
            "contract_multiplier": encode(row.contract_multiplier),
            "currency": row.currency,
            "session_type": row.session_type.value,
            "is_active": row.is_active,
        }

    @staticmethod
    def _daily(row, spot=None):
        close_basis = row.close - spot if row.close is not None and spot else None
        settlement_basis = (
            row.settlement_price - spot if row.settlement_price is not None and spot else None
        )
        return {
            name: encode(getattr(row, name))
            for name in (
                "contract_code",
                "contract_month",
                "trade_date",
                "session_type",
                "open",
                "high",
                "low",
                "close",
                "settlement_price",
                "change",
                "change_percent",
                "volume",
                "open_interest",
            )
        } | {
            "close_basis": encode(close_basis),
            "settlement_basis": encode(settlement_basis),
            "basis_definition": "futures close/settlement minus spot close",
            **metadata(row),
        }

    async def positions(self, product_code: str, window: int):
        if window not in (1, 5, 10, 20, 60):
            raise ValueError("window must be 1, 5, 10, 20 or 60")
        rows = await self.repository.positions(product_code, window + 1)
        by_institution = defaultdict(list)
        for row in rows:
            by_institution[row.institution_type].append(row)
        result = []
        for values in by_institution.values():
            values.sort(key=lambda x: x.trade_date)
            selected = values[-window:]
            first_index = values.index(selected[0])
            previous = values[first_index - 1] if first_index else None
            for row in selected:
                result.append(
                    {
                        "product_code": row.product_code,
                        "trade_date": row.trade_date.isoformat(),
                        "institution_type": row.institution_type.value,
                        **{
                            name: encode(getattr(row, name))
                            for name in (
                                "long_volume",
                                "short_volume",
                                "net_volume",
                                "long_amount",
                                "short_amount",
                                "net_amount",
                                "long_oi",
                                "short_oi",
                                "net_oi",
                                "long_oi_amount",
                                "short_oi_amount",
                                "net_oi_amount",
                            )
                        },
                        "long_oi_change": row.long_oi - previous.long_oi
                        if previous and row.long_oi is not None and previous.long_oi is not None
                        else None,
                        "short_oi_change": row.short_oi - previous.short_oi
                        if previous and row.short_oi is not None and previous.short_oi is not None
                        else None,
                        "net_oi_change": row.net_oi - previous.net_oi
                        if previous and row.net_oi is not None and previous.net_oi is not None
                        else None,
                        **metadata(row),
                    }
                )
                previous = row
        return sorted(result, key=lambda x: (x["trade_date"], x["institution_type"]))


class DerivativesRiskService:
    def __init__(self, repository: DerivativesRepository):
        self.repository = repository

    async def volatility(self, limit: int):
        rows = await self.repository.volatility("TAIWAN_VIX", limit)
        closes = [r.close for r in rows if r.close is not None]

        def percentile(window):
            sample = closes[-window:]
            if not sample or rows[-1].close is None:
                return None
            return (
                Decimal(sum(1 for value in sample if value <= rows[-1].close))
                / Decimal(len(sample))
                * 100
            )

        return [
            {
                "code": r.code,
                "trade_date": r.trade_date.isoformat(),
                "open": encode(r.open),
                "high": encode(r.high),
                "low": encode(r.low),
                "close": encode(r.close),
                **metadata(r),
            }
            for r in rows
        ] + (
            [
                {
                    "derived": True,
                    "percentile_20d": encode(percentile(20)),
                    "percentile_60d": encode(percentile(60)),
                }
            ]
            if rows
            else []
        )
