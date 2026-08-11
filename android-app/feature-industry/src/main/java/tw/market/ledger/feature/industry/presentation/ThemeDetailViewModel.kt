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
import tw.market.ledger.model.TaxonomyDetail
import tw.market.ledger.model.Theme
import javax.inject.Inject

sealed interface ThemeDetailUiState {
    data object Loading : ThemeDetailUiState
    data class Error(val message: String) : ThemeDetailUiState
    data class Success(val detail: TaxonomyDetail<Theme>) : ThemeDetailUiState
}

@HiltViewModel
class ThemeDetailViewModel @Inject constructor(
    private val repository: IndustryRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    val themeId: String = checkNotNull(savedStateHandle["id"])
    private val _uiState = MutableStateFlow<ThemeDetailUiState>(ThemeDetailUiState.Loading)
    val uiState: StateFlow<ThemeDetailUiState> = _uiState.asStateFlow()

    init {
        loadDetail()
    }

    fun loadDetail() {
        viewModelScope.launch {
            _uiState.value = ThemeDetailUiState.Loading
            repository.getThemeDetail(themeId)
                .onSuccess { detail ->
                    _uiState.value = ThemeDetailUiState.Success(detail)
                }
                .onFailure { error ->
                    _uiState.value = ThemeDetailUiState.Error(error.message ?: "無法載入題材明細")
                }
        }
    }
}
