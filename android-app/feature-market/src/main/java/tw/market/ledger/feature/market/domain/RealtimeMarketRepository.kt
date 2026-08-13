package tw.market.ledger.feature.market.domain

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeMarketSnapshot

interface RealtimeMarketRepository {
    val updates: Flow<String>
    val connection: StateFlow<RealtimeConnectionState>
    suspend fun snapshots(): List<RealtimeMarketSnapshot>
    fun subscribe()
}
