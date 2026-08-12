package tw.market.ledger.model

data class StrengthComponents(
    val momentumScore: String? = null,
    val breadthScore: String? = null,
    val technicalScore: String? = null,
    val institutionalScore: String? = null,
    val turnoverScore: String? = null,
)

data class TaxonomyStrength(
    val id: String,
    val taxonomyId: String,
    val taxonomyCode: String,
    val taxonomyName: String,
    val taxonomyType: String,
    val tradeDate: String,
    val window: Int,
    val equalWeightReturn: String,
    val marketCapWeightedReturn: String? = null,
    val totalMembers: Int,
    val validMembers: Int,
    val coverageRatio: String,
    val advancers: Int,
    val decliners: Int,
    val unchanged: Int,
    val advanceRatio: String,
    val aboveMa20Pct: String,
    val aboveMa60Pct: String,
    val foreignNetAmount: String,
    val investmentTrustNetAmount: String,
    val dealerNetAmount: String,
    val marginBalanceChange: String,
    val shortBalanceChange: String,
    val lendingBalanceChange: String? = null,
    val turnoverAmount: String? = null,
    val turnoverShare: String? = null,
    val turnoverMomentum: String? = null,
    val components: StrengthComponents,
    val strengthScore: String? = null,
    val componentCoverage: String,
    val rank: Int? = null,
    val algorithmVersion: String,
    val dataStatus: DataStatus,
    val asOf: String,
    val isStale: Boolean = false,
)

data class TaxonomyLeader(
    val securityId: String,
    val code: String,
    val name: String,
    val market: MarketCode,
    val returnPct: String,
    val latestClose: String? = null,
    val foreignNet: String? = null,
    val dataStatus: DataStatus,
)

data class TaxonomyStrengthDetail(
    val snapshot: TaxonomyStrength,
    val leaders: List<TaxonomyLeader>,
    val laggards: List<TaxonomyLeader>,
    val isStale: Boolean = false,
)
