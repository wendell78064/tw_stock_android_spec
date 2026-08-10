package tw.market.ledger.feature.market

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import tw.market.ledger.feature.market.domain.GetMarketOverviewUseCase
import tw.market.ledger.feature.market.domain.MarketRepository
import tw.market.ledger.feature.market.presentation.MarketDashboardUiState
import tw.market.ledger.feature.market.presentation.MarketDashboardViewModel
import tw.market.ledger.model.*

@OptIn(ExperimentalCoroutinesApi::class)
class MarketDashboardViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setup() = Dispatchers.setMain(dispatcher)
    @After fun close() = Dispatchers.resetMain()

    @Test fun partialOverviewAndWindowSwitchArePreserved() = runTest(dispatcher) {
        val repository = FakeRepository(status = DataStatus.PARTIAL)
        val viewModel = MarketDashboardViewModel(GetMarketOverviewUseCase(repository), repository)
        advanceUntilIdle()
        assertTrue(viewModel.uiState.value is MarketDashboardUiState.Partial)
        viewModel.selectWindow(60); advanceUntilIdle()
        assertEquals(60, viewModel.window.value)
        assertEquals(60, repository.requestedWindow)
    }

    @Test fun offlineWithoutCacheIsExplicitError() = runTest(dispatcher) {
        val repository = FakeRepository(fail = true)
        val viewModel = MarketDashboardViewModel(GetMarketOverviewUseCase(repository), repository)
        advanceUntilIdle()
        assertTrue(viewModel.uiState.value is MarketDashboardUiState.Error)
    }
}

private class FakeRepository(private val status: DataStatus = DataStatus.FINAL,
    private val fail: Boolean = false) : MarketRepository {
    var requestedWindow = 0
    override suspend fun overview(): MarketOverview {
        if (fail) throw IOException("offline")
        val index = MarketIndex("TAIEX", "加權指數", MarketCode.TWSE, "2026-08-07",
            "1", "2", "1", "2", "1", "1", "100", 1, "2026-08-07", status)
        return MarketOverview(listOf(index), emptyList(), emptyList(), emptyList(), emptyList(),
            index.asOf, status)
    }
    override suspend fun marketInstitutional(market: MarketCode, window: Int): List<InstitutionalPoint> {
        requestedWindow = window; return emptyList()
    }
    override suspend fun securityInstitutional(code: String, market: MarketCode, window: Int) = emptyList<InstitutionalPoint>()
    override suspend fun securityCredit(code: String, market: MarketCode, window: Int) = SecurityCredit(emptyList(), emptyList())
}
