package tw.market.ledger.feature.portfolio.data

import java.io.IOException
import tw.market.ledger.database.*
import tw.market.ledger.feature.portfolio.domain.*
import tw.market.ledger.model.*
import tw.market.ledger.network.*

class DefaultPortfolioRepository(
    private val api: PortfolioApi,
    private val dao: PortfolioDao,
) : PortfolioRepository {
    override suspend fun dashboard(): PortfolioDashboard = try {
        val portfolio = api.portfolios().data.firstOrNull { it.isDefault }
            ?: api.portfolios().data.first()
        val summary = api.summary(portfolio.id).data
        val holdings = api.positions(portfolio.id).data
        val transactions = api.transactions(portfolio.id).data
        dao.upsertSummary(summary.toEntity(portfolio.id))
        dao.clearHoldings(portfolio.id); dao.upsertHoldings(holdings.map { it.toEntity(portfolio.id) })
        dao.clearTransactions(portfolio.id); dao.upsertTransactions(transactions.map { it.toEntity() })
        PortfolioDashboard(portfolio.toDomain(), summary.toDomain(), holdings.map { it.toDomain() },
            transactions.map { it.toDomain() })
    } catch (error: IOException) {
        val id = apiPortfolioIdFromCache() ?: throw error
        val summary = dao.summary(id) ?: throw error
        PortfolioDashboard(Portfolio(id, "Default Portfolio", "TWD", true), summary.toDomain(true),
            dao.holdings(id).map { it.toDomain(true) }, dao.transactions(id).map { it.toDomain() })
    }

    private suspend fun apiPortfolioIdFromCache(): String? =
        listOf("00000000-0000-0000-0000-000000000001").firstOrNull { dao.summary(it) != null }

    override suspend fun addTransaction(portfolioId: String, draft: TransactionDraft): PortfolioTransaction =
        api.addTransaction(portfolioId, TransactionInputDto(draft.securityCode, draft.market?.name,
            draft.side.name, draft.executedAt, draft.quantityShares, draft.price, draft.fee,
            draft.lotType.name)).data.toDomain()

    override suspend fun deleteTransaction(portfolioId: String, transactionId: String) {
        api.deleteTransaction(portfolioId, transactionId)
    }
}

private fun PortfolioDto.toDomain() = Portfolio(id, name, baseCurrency, isDefault)
private fun PortfolioSummaryDto.toDomain(cache: Boolean = false) = PortfolioSummary(totalMarketValue,
    totalCostBasis, totalUnrealizedPnl, totalRealizedPnl, totalReturnPercent, holdingCount,
    priceAsOf, DataStatus.valueOf(dataStatus), taxHandling, cache)
private fun PortfolioHoldingDto.toDomain(cache: Boolean = false) = PortfolioHolding(securityCode,
    securityName, MarketCode.valueOf(market), quantityShares, averageCost, costBasis, realizedPnl,
    latestPrice, priceAsOf, DataStatus.valueOf(priceDataStatus), marketValue, unrealizedPnl,
    unrealizedReturnPercent, allocationPercent, cache)
private fun PortfolioTransactionDto.toDomain() = PortfolioTransaction(id, portfolioId, securityCode,
    securityName, MarketCode.valueOf(market), TransactionSide.valueOf(side), executedAt,
    quantityShares, price, fee, LotType.valueOf(lotType))
private fun PortfolioSummaryDto.toEntity(id: String) = PortfolioSummaryEntity(id, totalMarketValue,
    totalCostBasis, totalUnrealizedPnl, totalRealizedPnl, totalReturnPercent, holdingCount,
    priceAsOf, dataStatus, taxHandling)
private fun PortfolioHoldingDto.toEntity(id: String) = PortfolioHoldingEntity(id, securityCode,
    securityName, market, quantityShares, averageCost, costBasis, realizedPnl, latestPrice,
    priceAsOf, priceDataStatus, marketValue, unrealizedPnl, unrealizedReturnPercent, allocationPercent)
private fun PortfolioTransactionDto.toEntity() = PortfolioTransactionEntity(portfolioId, id,
    securityCode, securityName, market, side, executedAt, quantityShares, price, fee, lotType)
private fun PortfolioSummaryEntity.toDomain(cache: Boolean) = PortfolioSummary(totalMarketValue,
    totalCostBasis, totalUnrealizedPnl, totalRealizedPnl, totalReturnPercent, holdingCount,
    priceAsOf, DataStatus.valueOf(dataStatus), taxHandling, cache)
private fun PortfolioHoldingEntity.toDomain(cache: Boolean) = PortfolioHolding(securityCode,
    securityName, MarketCode.valueOf(market), quantityShares, averageCost, costBasis, realizedPnl,
    latestPrice, priceAsOf, DataStatus.valueOf(priceDataStatus), marketValue, unrealizedPnl,
    unrealizedReturnPercent, allocationPercent, cache)
private fun PortfolioTransactionEntity.toDomain() = PortfolioTransaction(id, portfolioId,
    securityCode, securityName, MarketCode.valueOf(market), TransactionSide.valueOf(side),
    executedAt, quantityShares, price, fee, LotType.valueOf(lotType))
