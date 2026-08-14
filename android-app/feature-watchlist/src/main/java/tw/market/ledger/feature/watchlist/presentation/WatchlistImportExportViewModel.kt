package tw.market.ledger.feature.watchlist.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.network.CsvImportTextInputDto
import tw.market.ledger.network.ImportExportApi
import tw.market.ledger.network.WatchlistApplyResultDto
import tw.market.ledger.network.WatchlistImportApplyInputDto
import tw.market.ledger.network.WatchlistImportPreviewDto

sealed interface WatchlistImportExportUiState {
    data object Idle : WatchlistImportExportUiState
    data object Loading : WatchlistImportExportUiState
    data class PreviewReady(val preview: WatchlistImportPreviewDto) : WatchlistImportExportUiState
    data class ExportReady(val fileName: String, val contentBytes: ByteArray, val mimeType: String) :
        WatchlistImportExportUiState {
        override fun equals(other: Any?): Boolean = other is ExportReady && fileName == other.fileName
        override fun hashCode(): Int = fileName.hashCode()
    }
    data class ApplySuccess(val result: WatchlistApplyResultDto) : WatchlistImportExportUiState
    data class Error(val message: String) : WatchlistImportExportUiState
}

@HiltViewModel
class WatchlistImportExportViewModel @Inject constructor(
    private val api: ImportExportApi,
) : ViewModel() {

    private val _state = MutableStateFlow<WatchlistImportExportUiState>(
        WatchlistImportExportUiState.Idle
    )
    val state: StateFlow<WatchlistImportExportUiState> = _state.asStateFlow()

    private var currentPreviewToken: String? = null

    fun resetState() {
        _state.value = WatchlistImportExportUiState.Idle
        currentPreviewToken = null
    }

    fun exportWatchlistsCsv() = viewModelScope.launch {
        _state.value = WatchlistImportExportUiState.Loading
        try {
            val bytes = api.exportWatchlists().bytes()
            _state.value = WatchlistImportExportUiState.ExportReady(
                fileName = "watchlists.csv",
                contentBytes = bytes,
                mimeType = "text/csv",
            )
        } catch (e: Exception) {
            _state.value = WatchlistImportExportUiState.Error(e.message ?: "匯出自選群組失敗")
        }
    }

    fun previewImportCsv(csvContent: String, mergeMode: String = "MERGE") = viewModelScope.launch {
        _state.value = WatchlistImportExportUiState.Loading
        try {
            val envelope = api.previewWatchlistImport(
                CsvImportTextInputDto(csvContent = csvContent, mergeMode = mergeMode)
            )
            currentPreviewToken = envelope.data.token
            _state.value = WatchlistImportExportUiState.PreviewReady(envelope.data)
        } catch (e: IOException) {
            _state.value = WatchlistImportExportUiState.Error("連線失敗，請檢查網路設定")
        } catch (e: Exception) {
            _state.value = WatchlistImportExportUiState.Error(e.message ?: "解析自選匯入檔失敗")
        }
    }

    fun applyImport(mergeMode: String = "MERGE") = viewModelScope.launch {
        val token = currentPreviewToken ?: return@launch
        _state.value = WatchlistImportExportUiState.Loading
        try {
            val envelope = api.applyWatchlistImport(
                WatchlistImportApplyInputDto(previewToken = token, mergeMode = mergeMode)
            )
            _state.value = WatchlistImportExportUiState.ApplySuccess(envelope.data)
        } catch (e: Exception) {
            _state.value = WatchlistImportExportUiState.Error(e.message ?: "套用自選匯入失敗")
        }
    }
}
