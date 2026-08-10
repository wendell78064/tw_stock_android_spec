package tw.market.ledger.feature.security.domain

import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security
import tw.market.ledger.model.SecuritySearchResult

data class SearchOutcome(val result: SecuritySearchResult, val fromCache: Boolean)
data class DetailOutcome(val security: Security, val fromCache: Boolean)

interface SecurityRepository {
    suspend fun search(query: String, market: MarketCode? = null, limit: Int = 20): SearchOutcome
    suspend fun detail(code: String, market: MarketCode): DetailOutcome
}

class SearchSecuritiesUseCase(private val repository: SecurityRepository) {
    suspend operator fun invoke(query: String, market: MarketCode? = null): SearchOutcome =
        repository.search(query.trim(), market)
}

class GetSecurityUseCase(private val repository: SecurityRepository) {
    suspend operator fun invoke(code: String, market: MarketCode): DetailOutcome =
        repository.detail(code, market)
}

