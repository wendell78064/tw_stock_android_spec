package tw.market.ledger.feature.security

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.security.domain.IntradayHistory
import tw.market.ledger.feature.security.domain.IntradayRepository
import tw.market.ledger.feature.security.presentation.IntradayChartScreen
import tw.market.ledger.feature.security.presentation.IntradayChartViewModel
import tw.market.ledger.feature.security.presentation.IntradayUiState
import tw.market.ledger.model.IntradayCandle
import tw.market.ledger.model.IntradayChartState
import tw.market.ledger.model.IntradayInterval
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeTradingSession

private fun intraday(close: String = "101", final: Boolean = false) = IntradayCandle(
    "sec_1234", "TWSE", "1234", IntradayInterval.ONE_MINUTE, RealtimeTradingSession.REGULAR,
    "2026-08-13T01:00:00Z", "2026-08-13T01:01:00Z", "100", "102", "99", close,
    40, null, 4, final, RealtimeDataStatus.LIVE, "FAKE_REALTIME_PROVIDER", "2026-08-13T01:00:55Z",
)

@OptIn(ExperimentalCoroutinesApi::class)
class IntradayChartViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private val repository = FakeIntradayRepository()
    @Before fun setup() = Dispatchers.setMain(dispatcher)
    @After fun teardown() = Dispatchers.resetMain()

    @Test fun initialHistoryActiveReplaceIntervalAndFollowLatest() = runTest(dispatcher) {
        val viewModel = IntradayChartViewModel(repository)
        viewModel.load("1234", MarketCode.TWSE)
        advanceUntilIdle()
        repository.updatesFlow.emit(intraday("103", true))
        advanceUntilIdle()
        val chart = (viewModel.state.value as IntradayUiState.Content).chart
        assertEquals(1, chart.candles.size)
        assertEquals("103", chart.candles.single().close)
        viewModel.setFollowLatest(false)
        assertEquals(false, (viewModel.state.value as IntradayUiState.Content).chart.followLatest)
        viewModel.selectInterval(IntradayInterval.FIVE_MINUTES)
        advanceUntilIdle()
        assertEquals(IntradayInterval.FIVE_MINUTES, (viewModel.state.value as IntradayUiState.Content).chart.interval)
    }
}

private class FakeIntradayRepository : IntradayRepository {
    val updatesFlow = MutableSharedFlow<IntradayCandle>(extraBufferCapacity = 4)
    override val updates = updatesFlow
    override val connection = MutableStateFlow(RealtimeConnectionState.CONNECTED)
    override suspend fun history(code: String, market: MarketCode, interval: IntradayInterval) =
        IntradayHistory(listOf(intraday().copy(interval = interval)), "2026-08-13T01:00:55Z", false)
    override fun subscribe(code: String, market: MarketCode) = Unit
    override fun unsubscribe(code: String, market: MarketCode) = Unit
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class IntradayChartComposeTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun intervalOhlcvVolumeAndLiveStateAreRendered() {
        composeRule.setContent {
            IntradayChartScreen(
                IntradayUiState.Content(IntradayChartState(listOf(intraday()), connection = RealtimeConnectionState.CONNECTED)),
                {}, {},
            )
        }
        composeRule.onNodeWithTag("intraday-1d-chart").assertIsDisplayed()
        composeRule.onNodeWithTag("intraday-1m").assertIsDisplayed()
        composeRule.onNodeWithText("LIVE").assertIsDisplayed()
        composeRule.onNodeWithText("成交量 40").assertIsDisplayed()
    }

    @Test fun unavailableIsExplicit() {
        composeRule.setContent { IntradayChartScreen(IntradayUiState.Unavailable, {}, {}) }
        composeRule.onNodeWithTag("intraday-unavailable").assertIsDisplayed()
    }
}
