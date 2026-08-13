package tw.market.ledger.feature.market.data

import tw.market.ledger.feature.market.domain.RealtimeMarketRepository
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeMarketSnapshot
import tw.market.ledger.network.RealtimeApi
import tw.market.ledger.network.RealtimeQuoteClient

class DefaultRealtimeMarketRepository(private val api: RealtimeApi, private val client: RealtimeQuoteClient) : RealtimeMarketRepository {
    override val updates = client.aggregateUpdates
    override val connection = client.connectionState
    override suspend fun snapshots() = api.getRealtimeMarkets().body()?.map {
        RealtimeMarketSnapshot(it.marketId, it.asOf, it.totalMembers, it.validMembers,
            it.quotedMembers, it.coverageRatio, it.advancers, it.decliners, it.unchanged,
            it.advanceRatio, it.turnoverAmount, RealtimeDataStatus.valueOf(it.dataStatus), it.provider, it.sourceType)
    } ?: emptyList()
    override fun subscribe() = client.subscribeChannels("market")
}
