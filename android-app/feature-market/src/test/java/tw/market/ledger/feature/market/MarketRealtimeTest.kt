package tw.market.ledger.feature.market

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.market.domain.RealtimeMarketRepository
import tw.market.ledger.feature.market.presentation.MarketRealtimePanel
import tw.market.ledger.feature.market.presentation.MarketRealtimeUiState
import tw.market.ledger.feature.market.presentation.MarketRealtimeViewModel
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeMarketSnapshot

private val marketSnapshot = RealtimeMarketSnapshot("TWSE", "2026-08-13T01:00:00Z", 3, 3, 3, "1", 2, 1, 0, "0.6667", "3000", RealtimeDataStatus.DELAYED, "FAKE", "FAKE")

@OptIn(ExperimentalCoroutinesApi::class)
class MarketRealtimeViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setup() = Dispatchers.setMain(dispatcher)
    @After fun cleanup() = Dispatchers.resetMain()
    @Test fun initialSnapshotIncrementalAndDisconnectStale() = runTest(dispatcher) {
        val repository = FakeRealtimeMarketRepository()
        val viewModel = MarketRealtimeViewModel(repository)
        runCurrent()
        assertTrue(viewModel.state.value is MarketRealtimeUiState.Content)
        repository.connectionFlow.value = RealtimeConnectionState.RECONNECTING
        runCurrent()
        assertTrue((viewModel.state.value as MarketRealtimeUiState.Content).stale)
    }
}

private class FakeRealtimeMarketRepository : RealtimeMarketRepository {
    val updatesFlow = MutableSharedFlow<String>()
    val connectionFlow = MutableStateFlow(RealtimeConnectionState.CONNECTED)
    override val updates = updatesFlow
    override val connection = connectionFlow
    override suspend fun snapshots() = listOf(marketSnapshot)
    override fun subscribe() = Unit
}

@RunWith(RobolectricTestRunner::class) @Config(sdk = [35])
class MarketRealtimeComposeTest {
    @get:Rule val compose = createComposeRule()
    @Test fun breadthIsVisible() {
        compose.setContent { MarketRealtimePanel(MarketRealtimeUiState.Content(listOf(marketSnapshot), RealtimeConnectionState.CONNECTED, false)) }
        compose.onNodeWithTag("realtime-market-breadth").assertIsDisplayed()
    }
}
