package tw.market.ledger.feature.security.data

import tw.market.ledger.feature.security.domain.IntradayHistory
import tw.market.ledger.feature.security.domain.IntradayRepository
import tw.market.ledger.model.IntradayCandle
import tw.market.ledger.model.IntradayInterval
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeTradingSession
import tw.market.ledger.network.IntradayCandleDto
import tw.market.ledger.network.RealtimeApi
import tw.market.ledger.network.RealtimeQuoteClient
import tw.market.ledger.network.RealtimeSubscriptionManager

class DefaultIntradayRepository(
    private val api: RealtimeApi,
    private val client: RealtimeQuoteClient,
    private val subscriptions: RealtimeSubscriptionManager,
) : IntradayRepository {
    override val updates = client.candlesFlow
    override val connection = client.connectionState

    override suspend fun history(code: String, market: MarketCode, interval: IntradayInterval): IntradayHistory {
        val response = api.getIntradayCandles(market.name, code, interval.apiValue)
        val body = response.body() ?: error("盤中資料不可用 (${response.code()})")
        return IntradayHistory(body.candles.map(::map), body.asOf, body.dataStatus != "LIVE")
    }

    override fun subscribe(code: String, market: MarketCode) = subscriptions.subscribe(market.name, code)
    override fun unsubscribe(code: String, market: MarketCode) = subscriptions.unsubscribe(market.name, code)

    private fun map(value: IntradayCandleDto) = IntradayCandle(
        value.securityId, value.marketId, value.code,
        IntradayInterval.entries.first { it.apiValue == value.interval },
        RealtimeTradingSession.valueOf(value.session), value.bucketStart, value.bucketEnd,
        value.open, value.high, value.low, value.close, value.volume, value.turnoverAmount,
        value.quoteCount, value.isFinal, RealtimeDataStatus.valueOf(value.dataStatus), value.provider, value.updatedAt,
    )
}
