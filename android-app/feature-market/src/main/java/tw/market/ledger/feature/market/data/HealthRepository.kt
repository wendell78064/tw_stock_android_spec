package tw.market.ledger.feature.market.data

import tw.market.ledger.feature.market.domain.FoundationRepository
import tw.market.ledger.network.HealthApi

class HealthRepository(private val api: HealthApi) : FoundationRepository {
    override suspend fun isBackendHealthy(): Boolean = api.health().status == "ok"
}

