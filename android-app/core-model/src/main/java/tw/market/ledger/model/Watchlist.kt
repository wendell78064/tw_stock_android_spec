package tw.market.ledger.model

data class Watchlist(val id: String, val name: String, val sortOrder: Int)

data class WatchlistItem(
    val id: String,
    val watchlistId: String,
    val securityCode: String,
    val securityName: String,
    val market: String,
    val sortOrder: Int,
    val note: String? = null,
    val targetPrice: String? = null,
    val stopPrice: String? = null,
    val addPrice: String? = null,
    val close: String? = null,
    val change: String? = null,
    val changePercent: String? = null,
    val priceAsOf: String? = null,
    val dataStatus: String = "UNAVAILABLE",
    val foreignNet: Long? = null,
    val marginBalanceChange: Long? = null,
    val priceAboveMa20: Boolean? = null,
)

enum class WatchlistSort { MANUAL, CODE, CHANGE_PERCENT, FOREIGN_NET }

data class WatchlistDashboard(
    val groups: List<Watchlist>,
    val selectedId: String?,
    val items: List<WatchlistItem>,
    val offline: Boolean = false,
)
