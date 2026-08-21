package tw.market.ledger.feature.security.data

import java.io.IOException
import tw.market.ledger.database.SecurityDao
import tw.market.ledger.feature.security.domain.DetailOutcome
import tw.market.ledger.feature.security.domain.SearchOutcome
import tw.market.ledger.feature.security.domain.SecurityRepository
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.SecuritySearchResult
import tw.market.ledger.network.SecurityApi

class DefaultSecurityRepository(
    private val api: SecurityApi,
    private val dao: SecurityDao,
) : SecurityRepository {
    override suspend fun search(query: String, market: MarketCode?, limit: Int): SearchOutcome {
        return try {
            val envelope = api.search(query, market?.name, limit = limit)
            val securities = envelope.data.map { it.toDomain() }
            dao.upsert(securities.map { it.toEntity() })
            SearchOutcome(
                SecuritySearchResult(securities, envelope.meta.asOf, DataStatus.valueOf(envelope.meta.dataStatus)),
                fromCache = false,
            )
        } catch (error: IOException) {
            val cached = dao.search(query, "$query%", "%$query%", market?.name, limit).map { it.toDomain() }
            if (cached.isEmpty()) throw error
            SearchOutcome(
                SecuritySearchResult(cached, cached.maxOf { it.asOf }, DataStatus.STALE),
                fromCache = true,
            )
        }
    }

    override suspend fun detail(code: String, market: MarketCode): DetailOutcome {
        return try {
            val security = api.detail(code, market.name).data.toDomain()
            dao.upsert(listOf(security.toEntity()))
            DetailOutcome(security, fromCache = false)
        } catch (error: IOException) {
            val cached = dao.detail(code, market.name)?.toDomain() ?: throw error
            DetailOutcome(cached, fromCache = true)
        }
    }

    override suspend fun analysisPrompt(code: String, market: MarketCode): tw.market.ledger.model.AnalysisPrompt {
        val envelope = api.analysisPrompt(code, market.name)
        return envelope.data.toDomain()
    }
}


