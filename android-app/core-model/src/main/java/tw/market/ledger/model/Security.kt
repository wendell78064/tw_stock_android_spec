package tw.market.ledger.model

enum class MarketCode { TWSE, TPEX }
enum class SecurityType { COMMON_STOCK }
enum class SecurityStatus { ACTIVE, INACTIVE }
enum class DataStatus { LIVE, DELAYED, PRELIMINARY, FINAL, STALE, PARTIAL, UNAVAILABLE }

data class ThemeRef(
    val id: String,
    val code: String,
    val name: String,
)

data class Security(
    val id: String,
    val code: String,
    val name: String,
    val market: MarketCode,
    val securityType: SecurityType,
    val status: SecurityStatus,
    val primaryIndustry: String?,
    val listingDate: String?,
    val isActive: Boolean,
    val asOf: String,
    val receivedAt: String,
    val dataStatus: DataStatus,
    val themes: List<ThemeRef> = emptyList(),
)

data class SecuritySearchResult(
    val securities: List<Security>,
    val asOf: String,
    val dataStatus: DataStatus,
)
