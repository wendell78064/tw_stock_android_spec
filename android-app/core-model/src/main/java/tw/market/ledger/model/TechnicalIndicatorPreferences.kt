package tw.market.ledger.model

data class MaSettings(val periods: List<Int> = listOf(5, 10, 20, 60, 120, 240))
data class EmaSettings(val periods: List<Int> = listOf(12, 26))
data class MacdSettings(val fast: Int = 12, val slow: Int = 26, val signal: Int = 9)
data class RsiSettings(val period: Int = 14)
data class KdSettings(val rsvPeriod: Int = 9, val kSmoothing: Int = 3, val dSmoothing: Int = 3)
data class BollingerSettings(val period: Int = 20, val standardDeviationMultiplier: String = "2")
data class AtrSettings(val period: Int = 14)
data class WilliamsRSettings(val period: Int = 14)

data class TechnicalIndicatorPreferences(
    val enabled: Set<String> = setOf("MA20", "RSI14"),
    val ma: MaSettings = MaSettings(),
    val ema: EmaSettings = EmaSettings(),
    val macd: MacdSettings = MacdSettings(),
    val rsi: RsiSettings = RsiSettings(),
    val kd: KdSettings = KdSettings(),
    val bollinger: BollingerSettings = BollingerSettings(),
    val atr: AtrSettings = AtrSettings(),
    val williamsR: WilliamsRSettings = WilliamsRSettings(),
) {
    fun validationError(): String? = when {
        ma.periods.isEmpty() || ma.periods.any { it <= 0 } -> "MA period 必須大於 0"
        ma.periods.distinct().size != ma.periods.size -> "MA period 不可重複"
        ema.periods.isEmpty() || ema.periods.any { it <= 0 } -> "EMA period 必須大於 0"
        rsi.period <= 0 -> "RSI period 必須大於 0"
        macd.fast <= 0 -> "MACD fast 必須大於 0"
        macd.slow <= macd.fast -> "MACD slow 必須大於 fast"
        macd.signal <= 0 -> "MACD signal 必須大於 0"
        kd.rsvPeriod <= 0 || kd.kSmoothing <= 0 || kd.dSmoothing <= 0 -> "KD 參數必須大於 0"
        bollinger.period <= 0 -> "Bollinger period 必須大於 0"
        (bollinger.standardDeviationMultiplier.toBigDecimalOrNull()?.signum() ?: 0) <= 0 ->
            "Bollinger 標準差倍數必須大於 0"
        atr.period <= 0 -> "ATR period 必須大於 0"
        williamsR.period <= 0 -> "Williams %R period 必須大於 0"
        else -> null
    }

    fun queryParameters(): Map<String, String> {
        if (copy(enabled = Default.enabled) == Default) return emptyMap()
        return mapOf(
        "ma_periods" to ma.periods.joinToString(","),
        "ema_periods" to ema.periods.joinToString(","),
        "rsi_period" to rsi.period.toString(),
        "macd_fast" to macd.fast.toString(), "macd_slow" to macd.slow.toString(),
        "macd_signal" to macd.signal.toString(), "kd_period" to kd.rsvPeriod.toString(),
        "kd_k_smoothing" to kd.kSmoothing.toString(), "kd_d_smoothing" to kd.dSmoothing.toString(),
        "bollinger_period" to bollinger.period.toString(),
        "bollinger_stddev" to bollinger.standardDeviationMultiplier,
        "atr_period" to atr.period.toString(), "williams_period" to williamsR.period.toString(),
        )
    }

    companion object { val Default = TechnicalIndicatorPreferences() }
}
