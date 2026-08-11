package tw.market.ledger.model

data class Industry(
    val id: String,
    val code: String,
    val name: String,
    val classificationSource: String,
    val memberCount: Int = 0,
)

data class Theme(
    val id: String,
    val code: String,
    val name: String,
    val description: String?,
    val classificationType: String,
    val memberCount: Int = 0,
    val createdAt: String? = null,
    val updatedAt: String? = null,
)

data class TaxonomyMember(
    val securityId: String,
    val code: String,
    val name: String,
    val market: MarketCode,
    val securityType: SecurityType = SecurityType.COMMON_STOCK,
    val isActive: Boolean = true,
    val close: String?,
    val change: String?,
    val changePercent: String?,
    val asOf: String?,
    val dataStatus: DataStatus,
)

data class TaxonomyDetail<T>(
    val taxonomy: T,
    val members: List<TaxonomyMember>,
    val asOf: String,
    val dataStatus: DataStatus,
    val isStale: Boolean = false,
)
