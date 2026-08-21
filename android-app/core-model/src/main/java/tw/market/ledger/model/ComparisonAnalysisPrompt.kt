package tw.market.ledger.model

data class ComparisonSecurityItem(
    val code: String,
    val market: MarketCode,
)

data class ComparisonAnalysisPrompt(
    val securities: List<Security>,
    val generatedAt: String,
    val prompt: String,
    val characterCount: Int,
    val dataStatus: DataStatus,
)
