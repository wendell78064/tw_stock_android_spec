package tw.market.ledger.feature.security

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import tw.market.ledger.feature.security.domain.DetailOutcome
import tw.market.ledger.feature.security.domain.GetAnalysisPromptUseCase
import tw.market.ledger.feature.security.domain.SearchOutcome
import tw.market.ledger.feature.security.domain.SecurityRepository
import tw.market.ledger.feature.security.presentation.SecurityAiPromptUiState
import tw.market.ledger.feature.security.presentation.SecurityAiPromptViewModel
import tw.market.ledger.model.AnalysisPrompt
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode

@OptIn(ExperimentalCoroutinesApi::class)
class SecurityAiPromptViewModelTest {
    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `load successful emits success ui state`() = runTest {
        val dummyPrompt = AnalysisPrompt(
            security = security("2330"),
            asOf = "2026-08-20T15:30:00Z",
            generatedAt = "2026-08-20T15:30:05Z",
            prompt = "【TW Market Ledger 智慧台股量化分析 Prompt】\n2330 台積電...",
            characterCount = 1500,
            dataStatus = DataStatus.FINAL,
            portfolioIncluded = false,
        )

        val fakeRepo = object : SecurityRepository {
            override suspend fun search(query: String, market: MarketCode?, limit: Int): SearchOutcome =
                throw UnsupportedOperationException()
            override suspend fun detail(code: String, market: MarketCode): DetailOutcome =
                throw UnsupportedOperationException()
            override suspend fun analysisPrompt(code: String, market: MarketCode): AnalysisPrompt =
                dummyPrompt
        }

        val viewModel = SecurityAiPromptViewModel(GetAnalysisPromptUseCase(fakeRepo))
        assertEquals(SecurityAiPromptUiState.Idle, viewModel.uiState.value)

        viewModel.load("2330", MarketCode.TWSE)
        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state is SecurityAiPromptUiState.Success)
        assertEquals(dummyPrompt, (state as SecurityAiPromptUiState.Success).prompt)
    }

    @Test
    fun `load failure emits error ui state`() = runTest {
        val fakeRepo = object : SecurityRepository {
            override suspend fun search(query: String, market: MarketCode?, limit: Int): SearchOutcome =
                throw UnsupportedOperationException()
            override suspend fun detail(code: String, market: MarketCode): DetailOutcome =
                throw UnsupportedOperationException()
            override suspend fun analysisPrompt(code: String, market: MarketCode): AnalysisPrompt =
                throw RuntimeException("Network timeout")
        }

        val viewModel = SecurityAiPromptViewModel(GetAnalysisPromptUseCase(fakeRepo))
        viewModel.load("2330", MarketCode.TWSE)
        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state is SecurityAiPromptUiState.Error)
        assertEquals("Network timeout", (state as SecurityAiPromptUiState.Error).message)
    }
}
