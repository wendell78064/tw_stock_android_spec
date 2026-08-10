package tw.market.ledger.feature.security.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import javax.inject.Inject
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import tw.market.ledger.feature.security.domain.SearchSecuritiesUseCase
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security

sealed interface SecuritySearchUiState {
    data object Idle : SecuritySearchUiState
    data object Loading : SecuritySearchUiState
    data object Empty : SecuritySearchUiState
    data class Error(val message: String) : SecuritySearchUiState
    data class Offline(val message: String) : SecuritySearchUiState
    data class Stale(val items: List<Security>, val asOf: String) : SecuritySearchUiState
    data class Success(val items: List<Security>, val asOf: String) : SecuritySearchUiState
}

@OptIn(FlowPreview::class)
@HiltViewModel
class SecuritySearchViewModel @Inject constructor(
    private val search: SearchSecuritiesUseCase,
) : ViewModel() {
    private val queryFlow = MutableStateFlow("")
    private val _uiState = MutableStateFlow<SecuritySearchUiState>(SecuritySearchUiState.Idle)
    val uiState: StateFlow<SecuritySearchUiState> = _uiState.asStateFlow()
    val query: StateFlow<String> = queryFlow.asStateFlow()
    private var market: MarketCode? = null

    init {
        viewModelScope.launch {
            queryFlow.debounce(350).distinctUntilChanged().collect { value ->
                if (value.length >= 2) execute(value)
                else _uiState.value = SecuritySearchUiState.Idle
            }
        }
    }

    fun onQueryChange(value: String) { queryFlow.value = value }
    fun onClear() { queryFlow.value = "" }
    fun onSearch() { if (queryFlow.value.length >= 2) viewModelScope.launch { execute(queryFlow.value) } }
    fun onMarketChange(value: MarketCode?) { market = value; onSearch() }

    private suspend fun execute(value: String) {
        _uiState.value = SecuritySearchUiState.Loading
        try {
            val outcome = search(value, market)
            _uiState.value = when {
                outcome.result.securities.isEmpty() -> SecuritySearchUiState.Empty
                outcome.fromCache -> SecuritySearchUiState.Stale(outcome.result.securities, outcome.result.asOf)
                else -> SecuritySearchUiState.Success(outcome.result.securities, outcome.result.asOf)
            }
        } catch (_: IOException) {
            _uiState.value = SecuritySearchUiState.Offline("目前離線，且沒有可用快取")
        } catch (error: Exception) {
            _uiState.value = SecuritySearchUiState.Error(error.message ?: "搜尋失敗")
        }
    }
}

