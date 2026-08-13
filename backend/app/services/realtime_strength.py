from decimal import ROUND_HALF_UP, Decimal
from time import monotonic

from app.domain.realtime import DataStatus, RealtimeQuote
from app.domain.realtime_strength import (
    RealtimeLeader,
    RealtimeMarketSnapshot,
    RealtimeStrengthComponents,
    RealtimeTaxonomySnapshot,
    RealtimeTaxonomyType,
)
from app.repositories.realtime_membership import RealtimeMembershipSnapshot
from app.services.realtime_cache import RealtimeCacheService

ZERO = Decimal("0")
HUNDRED = Decimal("100")
WEIGHTS = {
    "momentum": Decimal("0.35"),
    "breadth": Decimal("0.30"),
    "technical": Decimal("0.25"),
    "turnover": Decimal("0.10"),
}


class RealtimeIndustryStrengthScoringService:
    minimum_coverage = Decimal("0.60")

    @staticmethod
    def percentiles(values: dict[str, Decimal]) -> dict[str, Decimal]:
        if not values:
            return {}
        if len(values) == 1:
            return {next(iter(values)): Decimal("50.00")}
        ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
        result = {}
        for key, value in ordered:
            tied = [index for index, (_, candidate) in enumerate(ordered) if candidate == value]
            rank = Decimal(sum(tied)) / Decimal(len(tied))
            result[key] = (rank / Decimal(len(ordered) - 1) * HUNDRED).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        return result

    def score(self, snapshots: list[RealtimeTaxonomySnapshot]) -> list[RealtimeTaxonomySnapshot]:
        raw = {
            "momentum": {
                s.taxonomy_id: s.equal_weight_return
                for s in snapshots
                if s.equal_weight_return is not None
            },
            "breadth": {
                s.taxonomy_id: s.advance_ratio for s in snapshots if s.advance_ratio is not None
            },
            "technical": {
                s.taxonomy_id: (s.above_ma20_pct_realtime + s.above_ma60_pct_realtime) / 2
                for s in snapshots
                if s.above_ma20_pct_realtime is not None and s.above_ma60_pct_realtime is not None
            },
            "turnover": {
                s.taxonomy_id: s.turnover_share for s in snapshots if s.turnover_share is not None
            },
        }
        percentiles = {name: self.percentiles(values) for name, values in raw.items()}
        scored = []
        for snapshot in snapshots:
            values = {
                name: scores.get(snapshot.taxonomy_id) for name, scores in percentiles.items()
            }
            available = sum(
                (WEIGHTS[name] for name, value in values.items() if value is not None), ZERO
            )
            score = None
            if available >= self.minimum_coverage:
                score = (
                    sum(
                        (
                            values[name] * WEIGHTS[name]
                            for name in WEIGHTS
                            if values[name] is not None
                        ),
                        ZERO,
                    )
                    / available
                ).quantize(Decimal("0.01"))
            scored.append(
                snapshot.model_copy(
                    update={
                        "components": RealtimeStrengthComponents(**values),
                        "component_coverage": available,
                        "realtime_strength_score": score,
                        "data_status": snapshot.data_status
                        if score is not None
                        else DataStatus.STALE,
                    }
                )
            )
        scored.sort(
            key=lambda s: (
                s.realtime_strength_score is None,
                -(s.realtime_strength_score or ZERO),
                -(s.equal_weight_return or ZERO),
                s.taxonomy_id,
            )
        )
        return [
            item.model_copy(
                update={"rank": index if item.realtime_strength_score is not None else None}
            )
            for index, item in enumerate(scored, 1)
        ]


class RealtimeMarketAggregator:
    def __init__(self, memberships: RealtimeMembershipSnapshot):
        self.memberships = memberships
        self.quotes: dict[str, RealtimeQuote] = {}

    def accept(self, quote: RealtimeQuote) -> RealtimeMarketSnapshot:
        self.quotes[quote.composite_key] = quote
        members = [
            member
            for member in self.memberships.members.values()
            if member.market.upper() == quote.market_id.upper()
        ]
        quotes = [self.quotes[m.key] for m in members if m.key in self.quotes]
        valid = [q for q in quotes if q.previous_close is not None]
        advancers = sum(q.last_price > q.previous_close for q in valid)
        decliners = sum(q.last_price < q.previous_close for q in valid)
        unchanged = len(valid) - advancers - decliners
        total = len(members)
        ratio = Decimal(len(valid)) / Decimal(total) if total else ZERO
        turnover_values = [q.turnover_amount for q in valid if q.turnover_amount is not None]
        return RealtimeMarketSnapshot(
            market_id=quote.market_id.upper(),
            as_of=quote.received_at,
            exchange_timestamp=quote.exchange_timestamp,
            total_members=total,
            valid_members=len(valid),
            quoted_members=len(quotes),
            coverage_ratio=ratio,
            advancers=advancers,
            decliners=decliners,
            unchanged=unchanged,
            advance_ratio=Decimal(advancers) / Decimal(len(valid)) if valid else ZERO,
            decline_ratio=Decimal(decliners) / Decimal(len(valid)) if valid else ZERO,
            turnover_amount=sum(turnover_values, ZERO)
            if len(turnover_values) == len(valid) and valid
            else None,
            live_count=sum(q.data_status is DataStatus.LIVE for q in quotes),
            stale_count=sum(
                q.data_status in {DataStatus.STALE, DataStatus.DELAYED} for q in quotes
            ),
            unavailable_count=total - len(quotes),
            data_status=quote.data_status if ratio >= Decimal("0.60") else DataStatus.STALE,
            provider=quote.provider,
            source_type="FAKE" if quote.provider.startswith("FAKE") else "PRODUCTION",
        )


class RealtimeTaxonomyAggregator:
    ranking_publish_interval_seconds = 0.25

    def __init__(self, memberships: RealtimeMembershipSnapshot, cache: RealtimeCacheService):
        self.memberships = memberships
        self.cache = cache
        self.market = RealtimeMarketAggregator(memberships)
        self.scoring = RealtimeIndustryStrengthScoringService()
        self.snapshots: dict[tuple[RealtimeTaxonomyType, str], RealtimeTaxonomySnapshot] = {}
        self._last_ranking_publish: dict[RealtimeTaxonomyType, float] = {}
        self.metrics = {
            name: 0
            for name in (
                "market_snapshots_updated",
                "taxonomy_snapshots_updated",
                "taxonomy_rankings_updated",
                "taxonomy_membership_cache_hits",
                "taxonomy_membership_cache_misses",
                "realtime_strength_calculations",
                "realtime_strength_partial",
                "realtime_strength_unavailable",
                "ranking_updates_throttled",
            )
        }

    async def accept(self, quote: RealtimeQuote) -> None:
        market = self.market.accept(quote)
        await self.cache.save_market_snapshot(market)
        self.metrics["market_snapshots_updated"] += 1
        affected = self.memberships.by_security.get(quote.composite_key, set())
        self.metrics[
            "taxonomy_membership_cache_hits" if affected else "taxonomy_membership_cache_misses"
        ] += 1
        for taxonomy_key in affected:
            self.snapshots[taxonomy_key] = self._aggregate(taxonomy_key, quote)
            self.metrics["taxonomy_snapshots_updated"] += 1
        for taxonomy_type in {key[0] for key in affected}:
            ranking = self.scoring.score(
                [snapshot for key, snapshot in self.snapshots.items() if key[0] is taxonomy_type]
            )
            for snapshot in ranking:
                self.snapshots[(taxonomy_type, snapshot.taxonomy_id)] = snapshot
                await self.cache.save_taxonomy_snapshot(snapshot)
            self.metrics["realtime_strength_calculations"] += len(ranking)
            now = monotonic()
            last = self._last_ranking_publish.get(taxonomy_type)
            if last is not None and now - last < self.ranking_publish_interval_seconds:
                self.metrics["ranking_updates_throttled"] += 1
                continue
            await self.cache.save_taxonomy_ranking(taxonomy_type, ranking)
            self._last_ranking_publish[taxonomy_type] = now
            self.metrics["taxonomy_rankings_updated"] += 1

    def _aggregate(self, taxonomy_key, trigger: RealtimeQuote) -> RealtimeTaxonomySnapshot:
        taxonomy_type, taxonomy_id = taxonomy_key
        code, name, member_keys = self.memberships.taxonomies[taxonomy_key]
        quotes = [self.market.quotes[key] for key in member_keys if key in self.market.quotes]
        valid = [q for q in quotes if q.previous_close is not None and q.previous_close != ZERO]
        returns = [(q.last_price / q.previous_close) - Decimal("1") for q in valid]
        advancers = sum(value > ZERO for value in returns)
        decliners = sum(value < ZERO for value in returns)
        unchanged = len(returns) - advancers - decliners
        turnover = [q.turnover_amount for q in valid if q.turnover_amount is not None]
        leaders = sorted(zip(valid, returns, strict=True), key=lambda item: (item[1], item[0].code))

        def leader(item):
            q, value = item
            member = self.memberships.members[q.composite_key]
            return RealtimeLeader(
                security_id=member.security_id,
                market=member.market,
                code=member.code,
                name=member.name,
                last_price=q.last_price,
                change=q.last_price - q.previous_close,
                change_percent=value * HUNDRED,
                data_status=q.data_status,
            )

        total = len(member_keys)
        coverage = Decimal(len(valid)) / Decimal(total) if total else ZERO
        return RealtimeTaxonomySnapshot(
            taxonomy_type=taxonomy_type,
            taxonomy_id=taxonomy_id,
            code=code,
            name=name,
            as_of=trigger.received_at,
            total_members=total,
            valid_members=len(valid),
            quoted_members=len(quotes),
            coverage_ratio=coverage,
            equal_weight_return=sum(returns, ZERO) / Decimal(len(returns)) * HUNDRED
            if returns
            else None,
            advancers=advancers,
            decliners=decliners,
            unchanged=unchanged,
            advance_ratio=Decimal(advancers) / Decimal(len(valid)) if valid else None,
            turnover_amount=sum(turnover, ZERO) if len(turnover) == len(valid) and valid else None,
            leaders=[leader(item) for item in reversed(leaders[-5:])],
            laggards=[leader(item) for item in leaders[:5]],
            data_status=trigger.data_status if coverage >= Decimal("0.60") else DataStatus.STALE,
            provider=trigger.provider,
            source_type="FAKE" if trigger.provider.startswith("FAKE") else "PRODUCTION",
        )
