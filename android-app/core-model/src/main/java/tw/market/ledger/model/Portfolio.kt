package tw.market.ledger.model

enum class TransactionSide { BUY, SELL }
enum class LotType { ROUND_LOT, ODD_LOT }
enum class HoldingSort { MARKET_VALUE, PNL, RETURN, CODE }

data class Portfolio(
    val id: String,
    val name: String,
    val baseCurrency: String,
    val isDefault: Boolean,
)

data class PortfolioSummary(
    val totalMarketValue: String?,
    val totalCostBasis: String,
    val totalUnrealizedPnl: String?,
    val totalRealizedPnl: String,
    val totalReturnPercent: String?,
    val holdingCount: Int,
    val priceAsOf: String?,
    val dataStatus: DataStatus,
    val taxHandling: String = "NOT_INCLUDED",
    val fromCache: Boolean = false,
)

data class PortfolioHolding(
    val securityCode: String,
    val securityName: String,
    val market: MarketCode,
    val quantityShares: Long,
    val averageCost: String?,
    val costBasis: String,
    val realizedPnl: String,
    val latestPrice: String?,
    val priceAsOf: String?,
    val priceDataStatus: DataStatus,
    val marketValue: String?,
    val unrealizedPnl: String?,
    val unrealizedReturnPercent: String?,
    val allocationPercent: String?,
    val fromCache: Boolean = false,
)

data class PortfolioTransaction(
    val id: String,
    val portfolioId: String,
    val securityCode: String,
    val securityName: String,
    val market: MarketCode,
    val side: TransactionSide,
    val executedAt: String,
    val quantityShares: Long,
    val price: String,
    val fee: String,
    val lotType: LotType,
)

data class TransactionDraft(
    val securityCode: String,
    val market: MarketCode?,
    val side: TransactionSide,
    val executedAt: String,
    val quantityShares: Long,
    val price: String,
    val fee: String,
    val lotType: LotType,
)
