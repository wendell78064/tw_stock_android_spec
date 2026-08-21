package tw.market.ledger.feature.security

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import tw.market.ledger.feature.security.domain.DetailOutcome
import tw.market.ledger.feature.security.domain.SearchOutcome
import tw.market.ledger.feature.security.domain.SearchSecuritiesUseCase
import tw.market.ledger.feature.security.domain.SecurityRepository
import tw.market.ledger.feature.security.presentation.SecuritySearchUiState
import tw.market.ledger.feature.security.presentation.SecuritySearchViewModel
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.SecuritySearchResult

@OptIn(ExperimentalCoroutinesApi::class)
class SecuritySearchViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setup() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    @Test fun debounceWaitsThenPublishesSuccess() = runTest(dispatcher) {
        val viewModel = SecuritySearchViewModel(SearchSecuritiesUseCase(FakeRepository()))
        viewModel.onQueryChange("12")
        advanceTimeBy(349)
        assertTrue(viewModel.uiState.value is SecuritySearchUiState.Idle)
        advanceUntilIdle()
        assertTrue(viewModel.uiState.value is SecuritySearchUiState.Success)
    }

    @Test fun emptyAndErrorStatesAreExplicit() = runTest(dispatcher) {
        val empty = SecuritySearchViewModel(SearchSecuritiesUseCase(FakeRepository(empty = true)))
        empty.onQueryChange("12"); advanceUntilIdle()
        assertTrue(empty.uiState.value is SecuritySearchUiState.Empty)
        val error = SecuritySearchViewModel(SearchSecuritiesUseCase(FakeRepository(error = true)))
        error.onQueryChange("12"); advanceUntilIdle()
        assertTrue(error.uiState.value is SecuritySearchUiState.Offline)
    }
}

private class FakeRepository(private val empty: Boolean = false, private val error: Boolean = false) : SecurityRepository {
    override suspend fun search(query: String, market: MarketCode?, limit: Int): SearchOutcome {
        if (error) throw IOException("offline")
        val items = if (empty) emptyList() else listOf(security())
        return SearchOutcome(SecuritySearchResult(items, "2026-08-06T00:00:00Z", DataStatus.FINAL), false)
    }
    override suspend fun detail(code: String, market: MarketCode) = DetailOutcome(security(), false)
    override suspend fun analysisPrompt(code: String, market: MarketCode): tw.market.ledger.model.AnalysisPrompt =
        tw.market.ledger.model.AnalysisPrompt(
            security = security(),
            asOf = "2026-08-06T00:00:00Z",
            generatedAt = "2026-08-06T00:00:05Z",
            prompt = "PROMPT",
            characterCount = 6,
            dataStatus = DataStatus.FINAL,
            portfolioIncluded = false,
        )
}


