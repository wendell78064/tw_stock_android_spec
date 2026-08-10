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
import tw.market.ledger.feature.security.domain.GetSecurityUseCase
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security

sealed interface SecurityDetailUiState {
    data object Loading : SecurityDetailUiState
    data class Error(val message: String) : SecurityDetailUiState
    data class Offline(val message: String) : SecurityDetailUiState
    data class Stale(val security: Security) : SecurityDetailUiState
    data class Success(val security: Security) : SecurityDetailUiState
}

@HiltViewModel
class SecurityDetailViewModel @Inject constructor(
    private val detail: GetSecurityUseCase,
) : ViewModel() {
    private val _uiState = MutableStateFlow<SecurityDetailUiState>(SecurityDetailUiState.Loading)
    val uiState: StateFlow<SecurityDetailUiState> = _uiState.asStateFlow()

    fun load(code: String, market: MarketCode) {
        viewModelScope.launch {
            _uiState.value = SecurityDetailUiState.Loading
            try {
                val outcome = detail(code, market)
                _uiState.value = if (outcome.fromCache) SecurityDetailUiState.Stale(outcome.security)
                    else SecurityDetailUiState.Success(outcome.security)
            } catch (_: IOException) {
                _uiState.value = SecurityDetailUiState.Offline("目前離線，且沒有可用快取")
            } catch (error: Exception) {
                _uiState.value = SecurityDetailUiState.Error(error.message ?: "載入失敗")
            }
        }
    }
}

