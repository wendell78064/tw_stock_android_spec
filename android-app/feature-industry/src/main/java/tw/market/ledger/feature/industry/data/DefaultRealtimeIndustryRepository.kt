package tw.market.ledger.feature.industry.data

import tw.market.ledger.feature.industry.domain.RealtimeIndustryRepository
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeStrengthComponents
import tw.market.ledger.model.RealtimeTaxonomySnapshot
import tw.market.ledger.network.RealtimeApi
import tw.market.ledger.network.RealtimeQuoteClient
import tw.market.ledger.network.RealtimeTaxonomySnapshotDto

class DefaultRealtimeIndustryRepository(private val api: RealtimeApi, private val client: RealtimeQuoteClient) : RealtimeIndustryRepository {
    override val updates = client.aggregateUpdates
    override val connection = client.connectionState
    override suspend fun ranking(industry: Boolean, sort: String): List<RealtimeTaxonomySnapshot> {
        val response = if (industry) api.getRealtimeIndustries(sort) else api.getRealtimeThemes(sort)
        return response.body()?.data?.map(::map) ?: emptyList()
    }
    override fun subscribe() = client.subscribeChannels("industry_strength", "theme_strength")
    private fun map(it: RealtimeTaxonomySnapshotDto) = RealtimeTaxonomySnapshot(
        it.taxonomyType, it.taxonomyId, it.code, it.name, it.asOf, it.totalMembers,
        it.validMembers, it.coverageRatio, it.equalWeightReturn, it.advancers, it.decliners,
        it.unchanged, it.advanceRatio, it.turnoverAmount, it.aboveMa20PctRealtime,
        it.aboveMa60PctRealtime, RealtimeStrengthComponents(it.components.momentum,
            it.components.breadth, it.components.technical, it.components.turnover),
        it.realtimeStrengthScore, it.componentCoverage, it.rank,
        RealtimeDataStatus.valueOf(it.dataStatus), it.provider, it.sourceType, it.algorithmVersion,
    )
}
