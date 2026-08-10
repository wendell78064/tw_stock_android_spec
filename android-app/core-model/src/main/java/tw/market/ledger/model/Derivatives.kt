package tw.market.ledger.model

enum class FuturesRange { D5, D10, D30, Y1, Y5 }
enum class RollMethod { VOLUME, OPEN_INTEREST, EXPIRY }

data class FuturesProduct(
    val code: String, val name: String, val contractMultiplier: String,
    val currency: String, val isActive: Boolean,
)

data class FuturesQuote(
    val contractCode: String, val contractMonth: String, val tradeDate: String,
    val open: String?, val high: String?, val low: String?, val close: String?,
    val settlementPrice: String?, val change: String?, val changePercent: String?,
    val volume: Long?, val openInterest: Long?, val closeBasis: String?,
    val dataStatus: DataStatus, val asOf: String,
)

data class FuturesOverview(
    val product: FuturesProduct, val near: FuturesQuote?, val next: FuturesQuote?,
    val dataStatus: DataStatus, val fromCache: Boolean = false,
)

data class FuturesInstitutionalPosition(
    val tradeDate: String, val institutionType: InstitutionType,
    val longOi: Long?, val shortOi: Long?, val netOi: Long?, val netOiChange: Long?,
    val dataStatus: DataStatus,
)

data class ContinuousFuturesPoint(
    val tradeDate: String, val open: String?, val high: String?, val low: String?,
    val close: String?, val volume: Long?, val openInterest: Long?,
    val sourceContract: String, val rollDate: String?, val rollMethod: RollMethod,
)
