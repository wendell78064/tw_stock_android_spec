package tw.market.ledger.model

enum class RealtimeDataStatus {
    LIVE,
    STALE,
    DELAYED,
    UNAVAILABLE
}

enum class RealtimeConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    UNAVAILABLE
}

enum class RealtimeTradingSession {
    REGULAR,
    AFTER_HOURS,
    UNKNOWN
}

data class RealtimeQuote(
    val securityId: String,
    val marketId: String,
    val code: String,
    val exchangeTimestamp: String,
    val receivedAt: String,
    val lastPrice: String,
    val lastSize: Int = 0,
    val openPrice: String? = null,
    val highPrice: String? = null,
    val lowPrice: String? = null,
    val previousClose: String? = null,
    val totalVolume: Long = 0,
    val turnoverAmount: String? = null,
    val bidPrice: String? = null,
    val bidSize: Int? = null,
    val askPrice: String? = null,
    val askSize: Int? = null,
    val change: String? = null,
    val changePercent: String? = null,
    val session: RealtimeTradingSession = RealtimeTradingSession.REGULAR,
    val sequence: Long? = null,
    val dataStatus: RealtimeDataStatus = RealtimeDataStatus.LIVE,
    val provider: String = "UNKNOWN",
    val delaySeconds: Int = 0
) {
    val compositeKey: String get() = "${marketId.uppercase()}:${code.uppercase()}"
}
