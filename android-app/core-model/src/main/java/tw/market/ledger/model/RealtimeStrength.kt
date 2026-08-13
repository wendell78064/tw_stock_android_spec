package tw.market.ledger.model

data class RealtimeMarketSnapshot(
    val marketId: String, val asOf: String, val totalMembers: Int, val validMembers: Int,
    val quotedMembers: Int, val coverageRatio: String, val advancers: Int, val decliners: Int,
    val unchanged: Int, val advanceRatio: String, val turnoverAmount: String?,
    val dataStatus: RealtimeDataStatus, val provider: String, val sourceType: String,
)

data class RealtimeStrengthComponents(
    val momentum: String?, val breadth: String?, val technical: String?, val turnover: String?,
)

data class RealtimeTaxonomySnapshot(
    val taxonomyType: String, val taxonomyId: String, val code: String, val name: String,
    val asOf: String, val totalMembers: Int, val validMembers: Int, val coverageRatio: String,
    val equalWeightReturn: String?, val advancers: Int, val decliners: Int, val unchanged: Int,
    val advanceRatio: String?, val turnoverAmount: String?, val aboveMa20PctRealtime: String?,
    val aboveMa60PctRealtime: String?, val components: RealtimeStrengthComponents,
    val realtimeStrengthScore: String?, val componentCoverage: String, val rank: Int?,
    val dataStatus: RealtimeDataStatus, val provider: String, val sourceType: String,
    val algorithmVersion: String,
)
