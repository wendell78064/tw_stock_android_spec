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
import tw.market.ledger.model.TaxonomyStrengthDetail
import javax.inject.Inject

sealed interface StrengthDetailUiState {
    data object Loading : StrengthDetailUiState
    data class Error(val message: String) : StrengthDetailUiState
    data class Success(
        val detail: TaxonomyStrengthDetail,
        val history: List<TaxonomyStrength>,
        val window: Int,
        val isStale: Boolean = false,
    ) : StrengthDetailUiState
}

@HiltViewModel
class StrengthDetailViewModel @Inject constructor(
    private val repository: IndustryRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<StrengthDetailUiState>(StrengthDetailUiState.Loading)
    val uiState: StateFlow<StrengthDetailUiState> = _uiState.asStateFlow()

    private var currentId: String? = null
    private var isIndustry: Boolean = true
    private var currentWindow: Int = 20

    fun load(id: String, isIndustryTaxonomy: Boolean, window: Int = 20) {
        currentId = id
        isIndustry = isIndustryTaxonomy
        currentWindow = window

        viewModelScope.launch {
            _uiState.value = StrengthDetailUiState.Loading
            val detailRes = repository.getTaxonomyStrengthDetail(id, isIndustryTaxonomy, window)
            val historyRes = repository.getTaxonomyStrengthHistory(id, isIndustryTaxonomy, window, limit = 60)

            if (detailRes.isSuccess) {
                val detail = detailRes.getOrThrow()
                val history = historyRes.getOrNull()?.first ?: emptyList()
                val historyStale = historyRes.getOrNull()?.second ?: false
                _uiState.value = StrengthDetailUiState.Success(
                    detail = detail,
                    history = history,
                    window = window,
                    isStale = detail.isStale || historyStale,
                )
            } else {
                val error = detailRes.exceptionOrNull()?.message ?: "無法載入產業強弱明細"
                _uiState.value = StrengthDetailUiState.Error(error)
            }
        }
    }

    fun setWindow(window: Int) {
        val id = currentId ?: return
        load(id, isIndustry, window)
    }
}
