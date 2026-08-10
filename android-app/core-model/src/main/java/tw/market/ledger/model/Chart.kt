package tw.market.ledger.model

enum class ChartRange { ONE_DAY, FIVE_DAYS, TEN_DAYS, THIRTY_DAYS, ONE_YEAR, FIVE_YEARS }
enum class CandleInterval(val apiValue: String) { DAY("1d"), WEEK("1w"), MONTH("1mo") }
enum class PriceBasis { RAW, ADJUSTED }

data class Candle(
    val time: String,
    val open: String,
    val high: String,
    val low: String,
    val close: String,
    val volumeShares: Long?,
    val turnoverAmount: String?,
)

data class IndicatorValue(val name: String, val value: String?, val parameters: Map<String, Any> = emptyMap())
data class TechnicalPoint(
    val tradeDate: String,
    val priceBasis: PriceBasis,
    val algorithmVersion: String,
    val indicators: List<IndicatorValue>,
    val asOf: String,
    val dataStatus: DataStatus,
)

data class CandleResult(
    val candles: List<Candle>,
    val asOf: String,
    val dataStatus: DataStatus,
    val source: String,
    val displayNote: String?,
)
