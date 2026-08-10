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
    val basis = MutableStateFlow(PriceBasis.ADJUSTED)
    val indicators = MutableStateFlow(setOf("MA20", "RSI14"))
    val selected = MutableStateFlow<Candle?>(null)
    private var target: Pair<String, MarketCode>? = null

    init {
        viewModelScope.launch {
            settings.enabled.collect { saved ->
                indicators.value = saved
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
        viewModelScope.launch { settings.save(indicators.value) }
        refresh()
    }
    fun selectCandle(candle: Candle?) { selected.value = candle }

    private fun refresh() {
        val (code, market) = target ?: return
        viewModelScope.launch {
            _uiState.value = SecurityChartUiState.Loading
            try {
                val outcome = getChart(code, market, range.value, basis.value, indicators.value)
                _uiState.value = if (outcome.candles.candles.isEmpty()) SecurityChartUiState.Empty
                else SecurityChartUiState.Content(outcome.candles.candles, outcome.technicals,
                    outcome.candles.asOf, outcome.candles.dataStatus, outcome.fromCache,
                    outcome.candles.dataStatus == DataStatus.PARTIAL, outcome.candles.displayNote)
            } catch (_: IOException) {
                _uiState.value = SecurityChartUiState.Offline("目前離線，且沒有日 K 快取")
            } catch (error: Exception) {
                _uiState.value = SecurityChartUiState.Error(error.message ?: "走勢載入失敗")
            }
        }
    }
}
