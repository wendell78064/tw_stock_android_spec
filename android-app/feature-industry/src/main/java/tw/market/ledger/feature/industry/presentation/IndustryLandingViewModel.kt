package tw.market.ledger.feature.industry.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.industry.domain.IndustryRepository
import tw.market.ledger.model.Industry
import tw.market.ledger.model.Theme
import javax.inject.Inject

sealed interface IndustryLandingUiState {
    data object Loading : IndustryLandingUiState
    data class Error(val message: String) : IndustryLandingUiState
    data class Success(
        val industries: List<Industry>,
        val themes: List<Theme>,
        val isStale: Boolean = false,
    ) : IndustryLandingUiState
}

@HiltViewModel
class IndustryLandingViewModel @Inject constructor(
    private val repository: IndustryRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<IndustryLandingUiState>(IndustryLandingUiState.Loading)
    val uiState: StateFlow<IndustryLandingUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.value = IndustryLandingUiState.Loading
            val indResult = repository.getIndustries()
            val themeResult = repository.getThemes()

            if (indResult.isSuccess && themeResult.isSuccess) {
                val (industries, indStale) = indResult.getOrThrow()
                val (themes, themeStale) = themeResult.getOrThrow()
                _uiState.value = IndustryLandingUiState.Success(
                    industries = industries,
                    themes = themes,
                    isStale = indStale || themeStale,
                )
            } else {
                val error = indResult.exceptionOrNull()?.message
                    ?: themeResult.exceptionOrNull()?.message
                    ?: "無法載入產業與題材資料"
                _uiState.value = IndustryLandingUiState.Error(error)
            }
        }
    }
}
