package tw.market.ledger.feature.industry.domain

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeTaxonomySnapshot

interface RealtimeIndustryRepository {
    val updates: Flow<String>
    val connection: StateFlow<RealtimeConnectionState>
    suspend fun ranking(industry: Boolean, sort: String = "strength"): List<RealtimeTaxonomySnapshot>
    fun subscribe()
}
