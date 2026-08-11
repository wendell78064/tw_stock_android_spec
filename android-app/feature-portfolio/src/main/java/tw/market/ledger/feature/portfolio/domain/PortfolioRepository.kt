package tw.market.ledger.feature.portfolio.domain

import tw.market.ledger.model.*

data class PortfolioDashboard(
    val portfolio: Portfolio,
    val summary: PortfolioSummary,
    val holdings: List<PortfolioHolding>,
    val transactions: List<PortfolioTransaction>,
)

interface PortfolioRepository {
    suspend fun dashboard(): PortfolioDashboard
    suspend fun addTransaction(portfolioId: String, draft: TransactionDraft): PortfolioTransaction
    suspend fun deleteTransaction(portfolioId: String, transactionId: String)
}
