package tw.market.ledger.feature.portfolio.presentation

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
import tw.market.ledger.network.ImportApplyResultDto
import tw.market.ledger.network.ImportExportApi
import tw.market.ledger.network.PortfolioImportApplyInputDto
import tw.market.ledger.network.PortfolioImportPreviewDto

sealed interface ImportExportUiState {
    data object Idle : ImportExportUiState
    data object Loading : ImportExportUiState
    data class PreviewReady(val preview: PortfolioImportPreviewDto) : ImportExportUiState
    data class ExportReady(val fileName: String, val contentBytes: ByteArray, val mimeType: String) :
        ImportExportUiState {
        override fun equals(other: Any?): Boolean = other is ExportReady && fileName == other.fileName
        override fun hashCode(): Int = fileName.hashCode()
    }
    data class ApplySuccess(val result: ImportApplyResultDto) : ImportExportUiState
    data class Error(val message: String) : ImportExportUiState
}

@HiltViewModel
class PortfolioImportExportViewModel @Inject constructor(
    private val api: ImportExportApi,
) : ViewModel() {

    private val _state = MutableStateFlow<ImportExportUiState>(ImportExportUiState.Idle)
    val state: StateFlow<ImportExportUiState> = _state.asStateFlow()

    private var currentPreviewToken: String? = null

    fun resetState() {
        _state.value = ImportExportUiState.Idle
        currentPreviewToken = null
    }

    fun exportTransactionsCsv(portfolioId: String) = viewModelScope.launch {
        _state.value = ImportExportUiState.Loading
        try {
            val bytes = api.exportPortfolioTransactions(portfolioId).bytes()
            _state.value = ImportExportUiState.ExportReady(
                fileName = "portfolio_transactions_$portfolioId.csv",
                contentBytes = bytes,
                mimeType = "text/csv",
            )
        } catch (e: Exception) {
            _state.value = ImportExportUiState.Error(e.message ?: "匯出交易失敗")
        }
    }

    fun exportHoldingsCsv(portfolioId: String) = viewModelScope.launch {
        _state.value = ImportExportUiState.Loading
        try {
            val bytes = api.exportPortfolioHoldings(portfolioId).bytes()
            _state.value = ImportExportUiState.ExportReady(
                fileName = "portfolio_holdings_$portfolioId.csv",
                contentBytes = bytes,
                mimeType = "text/csv",
            )
        } catch (e: Exception) {
            _state.value = ImportExportUiState.Error(e.message ?: "匯出持股失敗")
        }
    }

    fun exportSummaryCsv(portfolioId: String) = viewModelScope.launch {
        _state.value = ImportExportUiState.Loading
        try {
            val bytes = api.exportPortfolioSummary(portfolioId).bytes()
            _state.value = ImportExportUiState.ExportReady(
                fileName = "portfolio_summary_$portfolioId.csv",
                contentBytes = bytes,
                mimeType = "text/csv",
            )
        } catch (e: Exception) {
            _state.value = ImportExportUiState.Error(e.message ?: "匯出摘要失敗")
        }
    }

    fun generatePdfReport(portfolioId: String) = viewModelScope.launch {
        _state.value = ImportExportUiState.Loading
        try {
            val bytes = api.generatePortfolioReport(portfolioId).bytes()
            _state.value = ImportExportUiState.ExportReady(
                fileName = "portfolio_report_$portfolioId.pdf",
                contentBytes = bytes,
                mimeType = "application/pdf",
            )
        } catch (e: Exception) {
            _state.value = ImportExportUiState.Error(e.message ?: "產生報表失敗")
        }
    }

    fun previewImportCsv(csvContent: String, portfolioId: String?) = viewModelScope.launch {
        _state.value = ImportExportUiState.Loading
        try {
            val envelope = api.previewPortfolioImport(
                CsvImportTextInputDto(csvContent = csvContent, portfolioId = portfolioId)
            )
            currentPreviewToken = envelope.data.token
            _state.value = ImportExportUiState.PreviewReady(envelope.data)
        } catch (e: IOException) {
            _state.value = ImportExportUiState.Error("連線失敗，請檢查網路設定")
        } catch (e: Exception) {
            _state.value = ImportExportUiState.Error(e.message ?: "解析匯入檔失敗")
        }
    }

    fun applyImport(portfolioId: String) = viewModelScope.launch {
        val token = currentPreviewToken ?: return@launch
        _state.value = ImportExportUiState.Loading
        try {
            val envelope = api.applyPortfolioImport(
                PortfolioImportApplyInputDto(previewToken = token, portfolioId = portfolioId)
            )
            _state.value = ImportExportUiState.ApplySuccess(envelope.data)
        } catch (e: Exception) {
            _state.value = ImportExportUiState.Error(e.message ?: "套用匯入失敗")
        }
    }
}
