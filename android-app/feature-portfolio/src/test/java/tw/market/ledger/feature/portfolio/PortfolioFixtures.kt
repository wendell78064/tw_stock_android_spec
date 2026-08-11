package tw.market.ledger.feature.portfolio

import tw.market.ledger.feature.portfolio.domain.PortfolioDashboard
import tw.market.ledger.model.*

val summary = PortfolioSummary("15000", "10000", "5000", "1000", "50", 1,
    "2026-08-10T00:00:00Z", DataStatus.FINAL)
val holding = PortfolioHolding("2330", "台積電", MarketCode.TWSE, 1000, "10", "10000",
    "1000", "15", "2026-08-10T00:00:00Z", DataStatus.FINAL, "15000", "5000",
    "50", "100")
val transaction = PortfolioTransaction("tx1", "p1", "2330", "台積電", MarketCode.TWSE,
    TransactionSide.BUY, "2026-08-01T09:00:00+08:00", 1000, "10", "0", LotType.ROUND_LOT)
val dashboard = PortfolioDashboard(Portfolio("p1", "Default", "TWD", true), summary,
    listOf(holding), listOf(transaction))
