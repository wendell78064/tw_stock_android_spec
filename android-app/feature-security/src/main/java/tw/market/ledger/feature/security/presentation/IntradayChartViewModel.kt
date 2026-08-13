package tw.market.ledger.feature.security.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.security.domain.IntradayRepository
import tw.market.ledger.model.IntradayChartState
import tw.market.ledger.model.IntradayInterval
import tw.market.ledger.model.MarketCode

sealed interface IntradayUiState {
    data object Loading : IntradayUiState
    data class Content(val chart: IntradayChartState) : IntradayUiState
    data class Error(val message: String) : IntradayUiState
    data object Unavailable : IntradayUiState
}

@HiltViewModel
class IntradayChartViewModel @Inject constructor(private val repository: IntradayRepository) : ViewModel() {
    private val _state = MutableStateFlow<IntradayUiState>(IntradayUiState.Loading)
    val state = _state.asStateFlow()
    private var target: Pair<String, MarketCode>? = null
    private var updateJob: Job? = null

    fun load(code: String, market: MarketCode, interval: IntradayInterval = IntradayInterval.ONE_MINUTE) {
        target?.let { repository.unsubscribe(it.first, it.second) }
        target = code to market
        repository.subscribe(code, market)
        updateJob?.cancel()
        updateJob = viewModelScope.launch {
            repository.updates.collect { candle ->
                if (candle.code == code && candle.marketId == market.name && candle.interval == interval) update(candle)
            }
        }
        selectInterval(interval)
    }

    fun selectInterval(interval: IntradayInterval) {
        val (code, market) = target ?: return
        viewModelScope.launch {
            _state.value = IntradayUiState.Loading
            try {
                val history = repository.history(code, market, interval)
                _state.value = IntradayUiState.Content(IntradayChartState(history.candles, interval, repository.connection.value, true, history.asOf, history.partial))
            } catch (error: Exception) {
                _state.value = IntradayUiState.Unavailable
            }
        }
    }

    fun setFollowLatest(value: Boolean) {
        val content = _state.value as? IntradayUiState.Content ?: return
        _state.value = content.copy(chart = content.chart.copy(followLatest = value))
    }

    private fun update(candle: tw.market.ledger.model.IntradayCandle) {
        val content = _state.value as? IntradayUiState.Content ?: return
        val rows = content.chart.candles.toMutableList()
        val index = rows.indexOfFirst { it.bucketKey == candle.bucketKey }
        if (index >= 0) rows[index] = candle else rows.add(candle)
        _state.value = content.copy(chart = content.chart.copy(candles = rows, asOf = candle.updatedAt, partial = candle.dataStatus.name != "LIVE"))
    }

    override fun onCleared() { target?.let { repository.unsubscribe(it.first, it.second) } }
}
