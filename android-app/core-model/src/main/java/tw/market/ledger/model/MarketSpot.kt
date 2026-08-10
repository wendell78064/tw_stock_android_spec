package tw.market.ledger.model

data class MarketIndex(
    val code: String, val name: String, val market: MarketCode, val tradeDate: String,
    val open: String?, val high: String?, val low: String?, val close: String?,
    val change: String?, val changePercent: String?, val turnoverAmount: String?,
    val volume: Long?, val asOf: String, val dataStatus: DataStatus,
)
data class MarketBreadth(
    val market: MarketCode, val tradeDate: String, val advancers: Int?, val decliners: Int?,
    val unchanged: Int?, val limitUp: Int?, val limitDown: Int?, val totalTraded: Int?,
    val turnoverAmount: String?, val asOf: String, val dataStatus: DataStatus,
)
enum class InstitutionType { FOREIGN, INVESTMENT_TRUST, DEALER, TOTAL }
enum class DealerSubtype { PROPRIETARY, HEDGE, TOTAL }
data class InstitutionalPoint(
    val market: MarketCode, val securityCode: String?, val tradeDate: String,
    val institutionType: InstitutionType, val dealerSubtype: DealerSubtype?, val buy: String?,
    val sell: String?, val net: String?, val cumulativeNet: String?,
    val consecutiveDirectionDays: Int, val asOf: String, val dataStatus: DataStatus,
)
data class MarginPoint(
    val tradeDate: String, val marginBalance: Long?, val marginBalanceChange: Long?,
    val shortBalance: Long?, val shortBalanceChange: Long?, val shortMarginRatio: String?,
    val asOf: String, val dataStatus: DataStatus,
)
data class LendingPoint(
    val tradeDate: String, val lendingSell: Long?, val lendingBalance: Long?,
    val lendingBalanceChange: Long?, val asOf: String, val dataStatus: DataStatus,
)
data class MarketOverview(
    val indexes: List<MarketIndex>, val breadth: List<MarketBreadth>,
    val institutional: List<InstitutionalPoint>, val margins: List<MarginPoint>,
    val lending: List<LendingPoint>, val asOf: String?, val dataStatus: DataStatus,
    val fromCache: Boolean = false,
)
data class SecurityCredit(
    val margins: List<MarginPoint>, val lending: List<LendingPoint>, val fromCache: Boolean = false,
)
