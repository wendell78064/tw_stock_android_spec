package tw.market.ledger.feature.security.domain

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import tw.market.ledger.model.IntradayCandle
import tw.market.ledger.model.IntradayInterval
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.RealtimeConnectionState

data class IntradayHistory(val candles: List<IntradayCandle>, val asOf: String, val partial: Boolean)

interface IntradayRepository {
    val updates: Flow<IntradayCandle>
    val connection: StateFlow<RealtimeConnectionState>
    suspend fun history(code: String, market: MarketCode, interval: IntradayInterval): IntradayHistory
    fun subscribe(code: String, market: MarketCode)
    fun unsubscribe(code: String, market: MarketCode)
}
