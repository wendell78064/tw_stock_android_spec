package tw.market.ledger.feature.industry.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch
import tw.market.ledger.feature.industry.domain.RealtimeIndustryRepository
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeTaxonomySnapshot

sealed interface IndustryRealtimeUiState {
    data object Loading : IndustryRealtimeUiState
    data class Content(val rows: List<RealtimeTaxonomySnapshot>, val industry: Boolean, val stale: Boolean) : IndustryRealtimeUiState
    data object Unavailable : IndustryRealtimeUiState
}

@OptIn(FlowPreview::class)
@HiltViewModel
class IndustryRealtimeViewModel @Inject constructor(private val repository: RealtimeIndustryRepository) : ViewModel() {
    private val _state = MutableStateFlow<IndustryRealtimeUiState>(IndustryRealtimeUiState.Loading)
    val state = _state.asStateFlow()
    private var industry = true
    init {
        repository.subscribe(); refresh()
        viewModelScope.launch { repository.updates.debounce(500).collect { if (it.startsWith("taxonomy")) refresh() } }
        viewModelScope.launch { repository.connection.collect { connection ->
            val current = _state.value as? IndustryRealtimeUiState.Content
            if (current != null && connection != RealtimeConnectionState.CONNECTED) _state.value = current.copy(stale = true)
        } }
    }
    fun setType(value: Boolean) { industry = value; refresh() }
    fun refresh() = viewModelScope.launch {
        try { val rows = repository.ranking(industry); _state.value = if (rows.isEmpty()) IndustryRealtimeUiState.Unavailable else IndustryRealtimeUiState.Content(rows, industry, false) }
        catch (_: Exception) { _state.value = (_state.value as? IndustryRealtimeUiState.Content)?.copy(stale = true) ?: IndustryRealtimeUiState.Unavailable }
    }
}
