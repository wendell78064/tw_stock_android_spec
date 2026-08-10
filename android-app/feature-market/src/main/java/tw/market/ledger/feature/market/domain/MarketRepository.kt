package tw.market.ledger.feature.market.domain

import tw.market.ledger.model.*

interface MarketRepository {
    suspend fun overview(): MarketOverview
    suspend fun marketInstitutional(market: MarketCode, window: Int): List<InstitutionalPoint>
    suspend fun securityInstitutional(code: String, market: MarketCode, window: Int): List<InstitutionalPoint>
    suspend fun securityCredit(code: String, market: MarketCode, window: Int = 60): SecurityCredit
}
class GetMarketOverviewUseCase(private val repository: MarketRepository) {
    suspend operator fun invoke() = repository.overview()
}
