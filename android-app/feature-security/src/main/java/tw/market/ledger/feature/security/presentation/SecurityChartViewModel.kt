package tw.market.ledger.feature.security.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.security.domain.GetSecurityChartUseCase
import tw.market.ledger.feature.security.data.IndicatorSettings
import tw.market.ledger.model.Candle
import tw.market.ledger.model.ChartRange
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.PriceBasis
import tw.market.ledger.model.TechnicalPoint
import tw.market.ledger.model.TechnicalIndicatorPreferences

sealed interface IndicatorSettingsUiState {
    data object Loading : IndicatorSettingsUiState
    data class Loaded(val preferences: TechnicalIndicatorPreferences) : IndicatorSettingsUiState
    data class ValidationError(val preferences: TechnicalIndicatorPreferences, val message: String) : IndicatorSettingsUiState
    data object Saving : IndicatorSettingsUiState
    data class Saved(val preferences: TechnicalIndicatorPreferences) : IndicatorSettingsUiState
}

sealed interface SecurityChartUiState {
    data object Loading : SecurityChartUiState
    data object Empty : SecurityChartUiState
    data class Error(val message: String) : SecurityChartUiState
    data class Offline(val message: String) : SecurityChartUiState
    data class Content(
        val candles: List<Candle>, val technicals: List<TechnicalPoint>, val asOf: String,
        val status: DataStatus, val stale: Boolean, val partial: Boolean, val note: String?,
    ) : SecurityChartUiState
}

@HiltViewModel
class SecurityChartViewModel @Inject constructor(
    private val getChart: GetSecurityChartUseCase,
    private val settings: IndicatorSettings,
) : ViewModel() {
    private val _uiState = MutableStateFlow<SecurityChartUiState>(SecurityChartUiState.Loading)
    val uiState: StateFlow<SecurityChartUiState> = _uiState.asStateFlow()
    val range = MutableStateFlow(ChartRange.ONE_YEAR)
    val basis = MutableStateFlow(PriceBasis.RAW)
    val indicators = MutableStateFlow(setOf("MA20", "RSI14"))
    val preferences = MutableStateFlow(TechnicalIndicatorPreferences.Default)
    val settingsUiState = MutableStateFlow<IndicatorSettingsUiState>(IndicatorSettingsUiState.Loading)
    val selected = MutableStateFlow<Candle?>(null)
    private var target: Pair<String, MarketCode>? = null

    init {
        viewModelScope.launch {
            settings.preferences.collect { saved ->
                val changed = preferences.value != saved
                preferences.value = saved
                indicators.value = saved.enabled
                settingsUiState.value = IndicatorSettingsUiState.Loaded(saved)
                if (changed && target != null) refresh()
            }
        }
    }

    fun load(code: String, market: MarketCode) { target = code to market; refresh() }
    fun selectRange(value: ChartRange) { range.value = value; refresh() }
    fun selectBasis(value: PriceBasis) { basis.value = value; refresh() }
    fun toggleIndicator(name: String) {
        val next = indicators.value.toMutableSet()
        if (!next.add(name)) next.remove(name)
        val secondary = setOf("MACD", "RSI14", "KD_K", "ATR14", "OBV", "WILLIAMS_R")
        if (next.count { it in secondary } <= 2) indicators.value = next
        val updated = preferences.value.copy(enabled = indicators.value)
        preferences.value = updated
        viewModelScope.launch { settings.save(updated) }
        refresh()
    }
    fun savePreferences(value: TechnicalIndicatorPreferences) {
        val error = value.validationError()
        if (error != null) { settingsUiState.value = IndicatorSettingsUiState.ValidationError(value, error); return }
        viewModelScope.launch {
            settingsUiState.value = IndicatorSettingsUiState.Saving
            settings.save(value)
            preferences.value = value
            indicators.value = value.enabled
            settingsUiState.value = IndicatorSettingsUiState.Saved(value)
            refresh()
        }
    }
    fun resetAllPreferences() = savePreferences(TechnicalIndicatorPreferences.Default)
    fun selectCandle(candle: Candle?) { selected.value = candle }

    private fun refresh() {
        val (code, market) = target ?: return
        viewModelScope.launch {
            _uiState.value = SecurityChartUiState.Loading
            try {
                val outcome = getChart(code, market, range.value, basis.value, preferences.value)
                _uiState.value = if (outcome.candles.candles.isEmpty()) SecurityChartUiState.Empty
                else SecurityChartUiState.Content(outcome.candles.candles, outcome.technicals,
                    outcome.candles.asOf, outcome.candles.dataStatus, outcome.fromCache,
                    outcome.candles.dataStatus == DataStatus.PARTIAL, outcome.candles.displayNote)
            } catch (_: IOException) {
                _uiState.value = SecurityChartUiState.Offline("參數已儲存；離線時無法重新計算，原快取不得視為新參數結果")
            } catch (error: Exception) {
                _uiState.value = SecurityChartUiState.Error(error.message ?: "走勢載入失敗")
            }
        }
    }
}
