package tw.market.ledger.feature.watchlist

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
import tw.market.ledger.feature.watchlist.presentation.WatchlistImportExportUiState
import tw.market.ledger.feature.watchlist.presentation.WatchlistImportExportViewModel
import tw.market.ledger.network.CsvImportTextInputDto
import tw.market.ledger.network.ImportApplyResultEnvelopeDto
import tw.market.ledger.network.ImportExportApi
import tw.market.ledger.network.PortfolioImportApplyInputDto
import tw.market.ledger.network.PortfolioImportPreviewEnvelopeDto
import tw.market.ledger.network.WatchlistApplyResultDto
import tw.market.ledger.network.WatchlistApplyResultEnvelopeDto
import tw.market.ledger.network.WatchlistImportApplyInputDto
import tw.market.ledger.network.WatchlistImportPreviewDto
import tw.market.ledger.network.WatchlistImportPreviewEnvelopeDto

@OptIn(ExperimentalCoroutinesApi::class)
class WatchlistImportExportViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    private val fakeApi = object : ImportExportApi {
        override suspend fun exportPortfolioTransactions(portfolioId: String) =
            throw UnsupportedOperationException()

        override suspend fun exportPortfolioHoldings(portfolioId: String) =
            throw UnsupportedOperationException()

        override suspend fun exportPortfolioSummary(portfolioId: String) =
            throw UnsupportedOperationException()

        override suspend fun exportWatchlists() =
            "wl_csv_data".toResponseBody("text/csv".toMediaType())

        override suspend fun generatePortfolioReport(portfolioId: String) =
            throw UnsupportedOperationException()

        override suspend fun previewPortfolioImport(input: CsvImportTextInputDto): PortfolioImportPreviewEnvelopeDto =
            throw UnsupportedOperationException()

        override suspend fun applyPortfolioImport(input: PortfolioImportApplyInputDto): ImportApplyResultEnvelopeDto =
            throw UnsupportedOperationException()

        override suspend fun previewWatchlistImport(input: CsvImportTextInputDto) =
            WatchlistImportPreviewEnvelopeDto(
                WatchlistImportPreviewDto(
                    token = "wl_tok_123",
                    mergeMode = input.mergeMode,
                    totalRows = 1,
                    validRows = 1,
                    invalidRows = 0,
                    errors = emptyList(),
                )
            )

        override suspend fun applyWatchlistImport(input: WatchlistImportApplyInputDto) =
            WatchlistApplyResultEnvelopeDto(
                WatchlistApplyResultDto(
                    status = "APPLIED",
                    mergeMode = input.mergeMode,
                    groupsCount = 1,
                    itemsCount = 1,
                )
            )
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
    fun `exportWatchlistsCsv updates state to ExportReady`() = runTest(dispatcher) {
        val viewModel = WatchlistImportExportViewModel(fakeApi)
        viewModel.exportWatchlistsCsv()
        advanceUntilIdle()

        val state = viewModel.state.value
        assertTrue(state is WatchlistImportExportUiState.ExportReady)
        assertEquals("watchlists.csv", (state as WatchlistImportExportUiState.ExportReady).fileName)
    }

    @Test
    fun `preview and apply watchlist import updates state to ApplySuccess`() = runTest(dispatcher) {
        val viewModel = WatchlistImportExportViewModel(fakeApi)
        viewModel.previewImportCsv("csv_data", "MERGE")
        advanceUntilIdle()

        assertTrue(viewModel.state.value is WatchlistImportExportUiState.PreviewReady)

        viewModel.applyImport("MERGE")
        advanceUntilIdle()

        val state = viewModel.state.value
        assertTrue(state is WatchlistImportExportUiState.ApplySuccess)
        assertEquals(1, (state as WatchlistImportExportUiState.ApplySuccess).result.groupsCount)
    }
}
