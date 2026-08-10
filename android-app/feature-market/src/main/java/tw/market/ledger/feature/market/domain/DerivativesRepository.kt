package tw.market.ledger.feature.market.domain

import tw.market.ledger.model.*

interface DerivativesRepository {
    suspend fun overview(product: String): FuturesOverview
    suspend fun positions(product: String, window: Int): List<FuturesInstitutionalPosition>
    suspend fun continuous(product: String, range: FuturesRange, rollMethod: RollMethod): List<ContinuousFuturesPoint>
}

class GetFuturesOverviewUseCase(private val repository: DerivativesRepository) {
    suspend operator fun invoke(product: String) = repository.overview(product)
}
