package tw.market.ledger.feature.industry.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.industry.domain.IndustryRepository
import tw.market.ledger.model.TaxonomyStrength
import javax.inject.Inject

sealed interface StrengthRankingUiState {
    data object Loading : StrengthRankingUiState
    data class Error(val message: String) : StrengthRankingUiState
    data class Success(
        val strengths: List<TaxonomyStrength>,
        val window: Int,
        val sort: String,
        val isIndustry: Boolean,
        val isStale: Boolean = false,
    ) : StrengthRankingUiState
}

@HiltViewModel
class StrengthRankingViewModel @Inject constructor(
    private val repository: IndustryRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<StrengthRankingUiState>(StrengthRankingUiState.Loading)
    val uiState: StateFlow<StrengthRankingUiState> = _uiState.asStateFlow()

    private var currentWindow = 20
    private var currentSort = "strength"
    private var isIndustryTab = true

    init {
        loadStrengths()
    }

    fun setWindow(window: Int) {
        if (currentWindow != window) {
            currentWindow = window
            loadStrengths()
        }
    }

    fun setSort(sort: String) {
        if (currentSort != sort) {
            currentSort = sort
            loadStrengths()
        }
    }

    fun setTab(isIndustry: Boolean) {
        if (isIndustryTab != isIndustry) {
            isIndustryTab = isIndustry
            loadStrengths()
        }
    }

    fun loadStrengths() {
        viewModelScope.launch {
            _uiState.value = StrengthRankingUiState.Loading
            val result = if (isIndustryTab) {
                repository.getIndustryStrengths(window = currentWindow, sort = currentSort)
            } else {
                repository.getThemeStrengths(window = currentWindow, sort = currentSort)
            }

            if (result.isSuccess) {
                val (strengths, isStale) = result.getOrThrow()
                _uiState.value = StrengthRankingUiState.Success(
                    strengths = strengths,
                    window = currentWindow,
                    sort = currentSort,
                    isIndustry = isIndustryTab,
                    isStale = isStale,
                )
            } else {
                val error = result.exceptionOrNull()?.message ?: "無法載入強弱排行資料"
                _uiState.value = StrengthRankingUiState.Error(error)
            }
        }
    }
}
