package tw.market.ledger.feature.industry.presentation

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.industry.domain.IndustryRepository
import tw.market.ledger.model.Industry
import tw.market.ledger.model.TaxonomyDetail
import javax.inject.Inject

sealed interface IndustryDetailUiState {
    data object Loading : IndustryDetailUiState
    data class Error(val message: String) : IndustryDetailUiState
    data class Success(val detail: TaxonomyDetail<Industry>) : IndustryDetailUiState
}

@HiltViewModel
class IndustryDetailViewModel @Inject constructor(
    private val repository: IndustryRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    val industryId: String = checkNotNull(savedStateHandle["id"])
    private val _uiState = MutableStateFlow<IndustryDetailUiState>(IndustryDetailUiState.Loading)
    val uiState: StateFlow<IndustryDetailUiState> = _uiState.asStateFlow()

    init {
        loadDetail()
    }

    fun loadDetail() {
        viewModelScope.launch {
            _uiState.value = IndustryDetailUiState.Loading
            repository.getIndustryDetail(industryId)
                .onSuccess { detail ->
                    _uiState.value = IndustryDetailUiState.Success(detail)
                }
                .onFailure { error ->
                    _uiState.value = IndustryDetailUiState.Error(error.message ?: "無法載入產業明細")
                }
        }
    }
}
