from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.realtime import (
    DataStatus,
    IntradayCandle,
    IntradayInterval,
    RealtimeEventKind,
    RealtimeQuote,
)
from app.services.realtime_cache import RealtimeCacheService

TAIPEI = ZoneInfo("Asia/Taipei")


class IntradayCandleAggregator:
    def __init__(self, cache: RealtimeCacheService):
        self.cache = cache
        self.metrics = {
            name: 0
            for name in (
                "quotes_aggregated",
                "candles_1m_created",
                "candles_1m_updated",
                "candles_1m_finalized",
                "candles_5m_created",
                "candles_5m_finalized",
                "out_of_order_dropped",
                "volume_reset_detected",
                "aggregation_errors",
            )
        }

    @staticmethod
    def bucket(timestamp: datetime, interval: IntradayInterval) -> tuple[datetime, datetime]:
        local = timestamp.astimezone(TAIPEI)
        minute = local.minute - local.minute % interval.minutes
        start = local.replace(minute=minute, second=0, microsecond=0)
        end = start + timedelta(minutes=interval.minutes)
        return start.astimezone(UTC), end.astimezone(UTC)

    async def accept(self, quote: RealtimeQuote) -> list[IntradayCandle]:
        if quote.event_kind is RealtimeEventKind.SNAPSHOT:
            await self.cache.set_volume_baseline(quote)
            return []
        baseline = await self.cache.get_volume_baseline(quote)
        volume_delta = 0
        turnover_delta = None
        partial = False
        if baseline is not None:
            previous_volume, previous_turnover = baseline
            if quote.total_volume >= previous_volume:
                volume_delta = quote.total_volume - previous_volume
            else:
                partial = True
                self.metrics["volume_reset_detected"] += 1
            if (
                quote.turnover_amount is not None
                and previous_turnover is not None
                and quote.turnover_amount >= previous_turnover
            ):
                turnover_delta = quote.turnover_amount - previous_turnover
        await self.cache.set_volume_baseline(quote)
        one = await self._update_one_minute(quote, volume_delta, turnover_delta, partial)
        if one is None:
            return []
        five = await self._derive_five_minute(one)
        self.metrics["quotes_aggregated"] += 1
        return [one, five]

    async def finalize_session(
        self,
        market: str,
        code: str,
        session,
        closed_at: datetime,
    ) -> list[IntradayCandle]:
        """Finalize open buckets when the trading-calendar session-close event fires."""
        finalized = []
        for interval in IntradayInterval:
            candle = await self.cache.get_current_candle(interval, market, code, session)
            if candle is not None:
                candle = candle.model_copy(update={"is_final": True, "updated_at": closed_at})
                await self.cache.save_candle(candle)
                self.metrics[f"candles_{interval.value}_finalized"] += 1
                finalized.append(candle)
        return finalized

    async def _update_one_minute(
        self, quote: RealtimeQuote, volume: int, turnover, partial: bool
    ) -> IntradayCandle | None:
        start, end = self.bucket(quote.exchange_timestamp, IntradayInterval.ONE_MINUTE)
        current = await self.cache.get_current_candle(
            IntradayInterval.ONE_MINUTE, quote.market_id, quote.code, quote.session
        )
        if current and (
            quote.sequence is not None
            and current.last_sequence is not None
            and quote.sequence <= current.last_sequence
            or quote.exchange_timestamp < current.updated_at
        ):
            self.metrics["out_of_order_dropped"] += 1
            return None
        if current and current.bucket_start != start:
            current = current.model_copy(update={"is_final": True, "updated_at": quote.received_at})
            await self.cache.save_candle(current)
            self.metrics["candles_1m_finalized"] += 1
            current = None
        status = DataStatus.STALE if partial else quote.data_status
        if current is None:
            candle = IntradayCandle(
                security_id=quote.security_id,
                market_id=quote.market_id,
                code=quote.code,
                interval=IntradayInterval.ONE_MINUTE,
                session=quote.session,
                bucket_start=start,
                bucket_end=end,
                open=quote.last_price,
                high=quote.last_price,
                low=quote.last_price,
                close=quote.last_price,
                volume=volume,
                turnover_amount=turnover,
                first_sequence=quote.sequence,
                last_sequence=quote.sequence,
                quote_count=1,
                data_status=status,
                provider=quote.provider,
                created_at=quote.received_at,
                updated_at=quote.exchange_timestamp,
            )
            self.metrics["candles_1m_created"] += 1
        else:
            candle = current.model_copy(
                update={
                    "high": max(current.high, quote.last_price),
                    "low": min(current.low, quote.last_price),
                    "close": quote.last_price,
                    "volume": current.volume + volume,
                    "turnover_amount": (current.turnover_amount + turnover)
                    if current.turnover_amount is not None and turnover is not None
                    else None,
                    "last_sequence": quote.sequence,
                    "quote_count": current.quote_count + 1,
                    "data_status": status,
                    "updated_at": quote.exchange_timestamp,
                }
            )
            self.metrics["candles_1m_updated"] += 1
        await self.cache.save_candle(candle)
        return candle

    async def _derive_five_minute(self, one: IntradayCandle) -> IntradayCandle:
        start, end = self.bucket(one.bucket_start, IntradayInterval.FIVE_MINUTES)
        minutes = await self.cache.get_candles(
            IntradayInterval.ONE_MINUTE, one.market_id, one.code, start=start, end=end, limit=5
        )
        minutes = [c for c in minutes if c.session == one.session]
        now = one.updated_at
        candle = IntradayCandle(
            security_id=one.security_id,
            market_id=one.market_id,
            code=one.code,
            interval=IntradayInterval.FIVE_MINUTES,
            session=one.session,
            bucket_start=start,
            bucket_end=end,
            open=minutes[0].open,
            high=max(c.high for c in minutes),
            low=min(c.low for c in minutes),
            close=minutes[-1].close,
            volume=sum(c.volume for c in minutes),
            turnover_amount=sum((c.turnover_amount for c in minutes), Decimal("0"))
            if all(c.turnover_amount is not None for c in minutes)
            else None,
            first_sequence=minutes[0].first_sequence,
            last_sequence=minutes[-1].last_sequence,
            quote_count=sum(c.quote_count for c in minutes),
            is_final=one.is_final and one.bucket_end == end,
            data_status=one.data_status,
            provider=one.provider,
            created_at=minutes[0].created_at,
            updated_at=now,
        )
        existing = await self.cache.get_current_candle(
            IntradayInterval.FIVE_MINUTES, one.market_id, one.code, one.session
        )
        if existing is None or existing.bucket_start != start:
            if existing is not None:
                await self.cache.save_candle(
                    existing.model_copy(update={"is_final": True, "updated_at": now})
                )
                self.metrics["candles_5m_finalized"] += 1
            self.metrics["candles_5m_created"] += 1
        await self.cache.save_candle(candle)
        return candle
