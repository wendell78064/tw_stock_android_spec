package tw.market.ledger.model

data class AnalysisPrompt(
    val security: Security,
    val asOf: String,
    val generatedAt: String,
    val prompt: String,
    val characterCount: Int,
    val dataStatus: DataStatus,
    val portfolioIncluded: Boolean,
)
