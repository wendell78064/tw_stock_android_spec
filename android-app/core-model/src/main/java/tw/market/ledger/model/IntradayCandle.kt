package tw.market.ledger.model

enum class IntradayInterval(val apiValue: String) { ONE_MINUTE("1m"), FIVE_MINUTES("5m") }

data class IntradayCandle(
    val securityId: String,
    val marketId: String,
    val code: String,
    val interval: IntradayInterval,
    val session: RealtimeTradingSession,
    val bucketStart: String,
    val bucketEnd: String,
    val open: String,
    val high: String,
    val low: String,
    val close: String,
    val volume: Long,
    val turnoverAmount: String?,
    val quoteCount: Int,
    val isFinal: Boolean,
    val dataStatus: RealtimeDataStatus,
    val provider: String,
    val updatedAt: String,
) {
    val bucketKey: String get() = "${interval.apiValue}:$session:$bucketStart"
}

data class IntradayChartState(
    val candles: List<IntradayCandle> = emptyList(),
    val interval: IntradayInterval = IntradayInterval.ONE_MINUTE,
    val connection: RealtimeConnectionState = RealtimeConnectionState.CONNECTING,
    val followLatest: Boolean = true,
    val asOf: String? = null,
    val partial: Boolean = false,
)
