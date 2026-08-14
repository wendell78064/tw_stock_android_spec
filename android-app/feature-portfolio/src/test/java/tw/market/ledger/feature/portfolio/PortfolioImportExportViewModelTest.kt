package tw.market.ledger.feature.portfolio

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import tw.market.ledger.feature.portfolio.presentation.ImportExportUiState
import tw.market.ledger.feature.portfolio.presentation.PortfolioImportExportViewModel
import tw.market.ledger.network.CsvImportTextInputDto
import tw.market.ledger.network.ImportApplyResultDto
import tw.market.ledger.network.ImportApplyResultEnvelopeDto
import tw.market.ledger.network.ImportExportApi
import tw.market.ledger.network.PortfolioImportApplyInputDto
import tw.market.ledger.network.PortfolioImportPreviewDto
import tw.market.ledger.network.PortfolioImportPreviewEnvelopeDto
import tw.market.ledger.network.WatchlistApplyResultEnvelopeDto
import tw.market.ledger.network.WatchlistImportApplyInputDto
import tw.market.ledger.network.WatchlistImportPreviewEnvelopeDto

@OptIn(ExperimentalCoroutinesApi::class)
class PortfolioImportExportViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    private val fakeApi = object : ImportExportApi {
        override suspend fun exportPortfolioTransactions(portfolioId: String) =
            "csv_data".toResponseBody("text/csv".toMediaType())

        override suspend fun exportPortfolioHoldings(portfolioId: String) =
            "holdings_data".toResponseBody("text/csv".toMediaType())

        override suspend fun exportPortfolioSummary(portfolioId: String) =
            "summary_data".toResponseBody("text/csv".toMediaType())

        override suspend fun exportWatchlists() =
            "wl_data".toResponseBody("text/csv".toMediaType())

        override suspend fun generatePortfolioReport(portfolioId: String) =
            "%PDF_data".toResponseBody("application/pdf".toMediaType())

        override suspend fun previewPortfolioImport(input: CsvImportTextInputDto) =
            PortfolioImportPreviewEnvelopeDto(
                PortfolioImportPreviewDto(
                    token = "tok123",
                    portfolioId = input.portfolioId,
                    totalRows = 1,
                    validRows = 1,
                    invalidRows = 0,
                    warningRows = 0,
                    duplicateRows = 0,
                    errors = emptyList(),
                    warnings = emptyList(),
                )
            )

        override suspend fun applyPortfolioImport(input: PortfolioImportApplyInputDto) =
            ImportApplyResultEnvelopeDto(
                ImportApplyResultDto(
                    status = "APPLIED",
                    insertedCount = 1,
                    skippedCount = 0,
                    totalTransactions = 1,
                )
            )

        override suspend fun previewWatchlistImport(input: CsvImportTextInputDto): WatchlistImportPreviewEnvelopeDto =
            throw UnsupportedOperationException()

        override suspend fun applyWatchlistImport(input: WatchlistImportApplyInputDto): WatchlistApplyResultEnvelopeDto =
            throw UnsupportedOperationException()
    }

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `exportTransactionsCsv updates state to ExportReady`() = runTest(dispatcher) {
        val viewModel = PortfolioImportExportViewModel(fakeApi)
        viewModel.exportTransactionsCsv("pf1")
        advanceUntilIdle()

        val state = viewModel.state.value
        assertTrue(state is ImportExportUiState.ExportReady)
        assertEquals("portfolio_transactions_pf1.csv", (state as ImportExportUiState.ExportReady).fileName)
    }

    @Test
    fun `generatePdfReport updates state to ExportReady with pdf mime`() = runTest(dispatcher) {
        val viewModel = PortfolioImportExportViewModel(fakeApi)
        viewModel.generatePdfReport("pf1")
        advanceUntilIdle()

        val state = viewModel.state.value
        assertTrue(state is ImportExportUiState.ExportReady)
        assertEquals("application/pdf", (state as ImportExportUiState.ExportReady).mimeType)
    }

    @Test
    fun `preview and apply import transitions to ApplySuccess`() = runTest(dispatcher) {
        val viewModel = PortfolioImportExportViewModel(fakeApi)
        viewModel.previewImportCsv("csv_text", "pf1")
        advanceUntilIdle()

        assertTrue(viewModel.state.value is ImportExportUiState.PreviewReady)

        viewModel.applyImport("pf1")
        advanceUntilIdle()

        val finalState = viewModel.state.value
        assertTrue(finalState is ImportExportUiState.ApplySuccess)
        assertEquals(1, (finalState as ImportExportUiState.ApplySuccess).result.insertedCount)
    }
}
