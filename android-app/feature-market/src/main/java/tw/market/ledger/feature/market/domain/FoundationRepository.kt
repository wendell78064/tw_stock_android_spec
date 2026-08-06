package tw.market.ledger.feature.market.domain

interface FoundationRepository {
    suspend fun isBackendHealthy(): Boolean
}

