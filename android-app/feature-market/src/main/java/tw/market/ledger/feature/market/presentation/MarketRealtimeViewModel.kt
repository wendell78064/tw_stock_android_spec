package tw.market.ledger.feature.market.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch
import tw.market.ledger.feature.market.domain.RealtimeMarketRepository
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeMarketSnapshot

sealed interface MarketRealtimeUiState {
    data object Loading : MarketRealtimeUiState
    data class Content(val snapshots: List<RealtimeMarketSnapshot>, val connection: RealtimeConnectionState, val stale: Boolean) : MarketRealtimeUiState
    data object Unavailable : MarketRealtimeUiState
}

@HiltViewModel
@OptIn(FlowPreview::class)
class MarketRealtimeViewModel @Inject constructor(private val repository: RealtimeMarketRepository) : ViewModel() {
    private val _state = MutableStateFlow<MarketRealtimeUiState>(MarketRealtimeUiState.Loading)
    val state = _state.asStateFlow()
    init {
        repository.subscribe(); refresh()
        viewModelScope.launch { repository.updates.debounce(500).collect { if (it.startsWith("market")) refresh() } }
        viewModelScope.launch { repository.connection.collect { connection ->
            val current = _state.value as? MarketRealtimeUiState.Content
            if (current != null) _state.value = current.copy(connection = connection, stale = connection != RealtimeConnectionState.CONNECTED)
        } }
    }
    fun refresh() = viewModelScope.launch {
        try { val rows = repository.snapshots(); _state.value = if (rows.isEmpty()) MarketRealtimeUiState.Unavailable else MarketRealtimeUiState.Content(rows, repository.connection.value, false) }
        catch (_: Exception) { _state.value = (_state.value as? MarketRealtimeUiState.Content)?.copy(stale = true) ?: MarketRealtimeUiState.Unavailable }
    }
}
