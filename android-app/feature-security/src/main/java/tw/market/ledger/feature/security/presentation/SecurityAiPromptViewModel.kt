package tw.market.ledger.feature.security.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.security.domain.GetAnalysisPromptUseCase
import tw.market.ledger.model.AnalysisPrompt
import tw.market.ledger.model.MarketCode

sealed interface SecurityAiPromptUiState {
    data object Idle : SecurityAiPromptUiState
    data object Loading : SecurityAiPromptUiState
    data class Success(val prompt: AnalysisPrompt) : SecurityAiPromptUiState
    data class Error(val message: String) : SecurityAiPromptUiState
}

@HiltViewModel
class SecurityAiPromptViewModel @Inject constructor(
    private val getAnalysisPrompt: GetAnalysisPromptUseCase,
) : ViewModel() {
    private val _uiState = MutableStateFlow<SecurityAiPromptUiState>(SecurityAiPromptUiState.Idle)
    val uiState: StateFlow<SecurityAiPromptUiState> = _uiState.asStateFlow()

    fun load(code: String, market: MarketCode) {
        viewModelScope.launch {
            _uiState.value = SecurityAiPromptUiState.Loading
            try {
                val prompt = getAnalysisPrompt(code, market)
                _uiState.value = SecurityAiPromptUiState.Success(prompt)
            } catch (e: Exception) {
                _uiState.value = SecurityAiPromptUiState.Error(e.message ?: "無法載入 AI 分析 Prompt")
            }
        }
    }
}
