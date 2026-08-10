package tw.market.ledger.feature.security.data

import android.content.Context
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import tw.market.ledger.model.*

private val Context.indicatorDataStore by preferencesDataStore("indicator-settings")

class IndicatorSettings(private val context: Context) {
    private fun key(name: String) = stringPreferencesKey(name)
    val preferences: Flow<TechnicalIndicatorPreferences> = context.indicatorDataStore.data.map { values ->
        fun ints(name: String, defaults: List<Int>) = values[key(name)]?.split(",")
            ?.mapNotNull(String::toIntOrNull)?.takeIf(List<Int>::isNotEmpty) ?: defaults
        fun int(name: String, default: Int) = values[key(name)]?.toIntOrNull() ?: default
        val defaults = TechnicalIndicatorPreferences.Default
        TechnicalIndicatorPreferences(
            enabled = values[key("enabled")]?.split(",")?.filter(String::isNotBlank)?.toSet() ?: defaults.enabled,
            ma = MaSettings(ints("ma", defaults.ma.periods)), ema = EmaSettings(ints("ema", defaults.ema.periods)),
            macd = MacdSettings(int("macd_fast", 12), int("macd_slow", 26), int("macd_signal", 9)),
            rsi = RsiSettings(int("rsi", 14)),
            kd = KdSettings(int("kd_period", 9), int("kd_k", 3), int("kd_d", 3)),
            bollinger = BollingerSettings(int("bb_period", 20), values[key("bb_stddev")] ?: "2"),
            atr = AtrSettings(int("atr", 14)), williamsR = WilliamsRSettings(int("williams", 14)),
        )
    }

    suspend fun save(value: TechnicalIndicatorPreferences) {
        require(value.validationError() == null) { value.validationError()!! }
        context.indicatorDataStore.edit {
            it[key("enabled")] = value.enabled.sorted().joinToString(",")
            it[key("ma")] = value.ma.periods.joinToString(","); it[key("ema")] = value.ema.periods.joinToString(",")
            it[key("macd_fast")] = value.macd.fast.toString(); it[key("macd_slow")] = value.macd.slow.toString()
            it[key("macd_signal")] = value.macd.signal.toString(); it[key("rsi")] = value.rsi.period.toString()
            it[key("kd_period")] = value.kd.rsvPeriod.toString(); it[key("kd_k")] = value.kd.kSmoothing.toString()
            it[key("kd_d")] = value.kd.dSmoothing.toString(); it[key("bb_period")] = value.bollinger.period.toString()
            it[key("bb_stddev")] = value.bollinger.standardDeviationMultiplier
            it[key("atr")] = value.atr.period.toString(); it[key("williams")] = value.williamsR.period.toString()
        }
    }

    suspend fun resetAll() = save(TechnicalIndicatorPreferences.Default)
}
