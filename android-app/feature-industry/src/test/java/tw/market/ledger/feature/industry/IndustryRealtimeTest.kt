package tw.market.ledger.feature.industry

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.industry.presentation.IndustryRealtimePanel
import tw.market.ledger.feature.industry.presentation.IndustryRealtimeUiState
import tw.market.ledger.feature.industry.presentation.IndustryRealtimeViewModel
import tw.market.ledger.feature.industry.domain.RealtimeIndustryRepository
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeStrengthComponents
import tw.market.ledger.model.RealtimeTaxonomySnapshot

private val taxonomy = RealtimeTaxonomySnapshot("INDUSTRY", "i1", "I1", "半導體", "2026-08-13", 10, 8, "0.8", "1.2", 6, 2, 0, "0.75", null, null, null, RealtimeStrengthComponents("82", "76", null, null), "79", "0.65", 1, RealtimeDataStatus.DELAYED, "FAKE", "FAKE", "twml-industry-realtime-strength-v1")

@OptIn(ExperimentalCoroutinesApi::class)
class IndustryRealtimeViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setup() = Dispatchers.setMain(dispatcher)
    @After fun cleanup() = Dispatchers.resetMain()
    @Test fun initialRankingModeSwitchAndDisconnectStale() = runTest(dispatcher) {
        val repository = FakeRealtimeIndustryRepository()
        val viewModel = IndustryRealtimeViewModel(repository)
        runCurrent()
        viewModel.setType(false)
        runCurrent()
        assertFalse((viewModel.state.value as IndustryRealtimeUiState.Content).industry)
        repository.connectionFlow.value = RealtimeConnectionState.RECONNECTING
        runCurrent()
        assert((viewModel.state.value as IndustryRealtimeUiState.Content).stale)
    }
}

private class FakeRealtimeIndustryRepository : RealtimeIndustryRepository {
    override val updates = MutableSharedFlow<String>()
    val connectionFlow = MutableStateFlow(RealtimeConnectionState.CONNECTED)
    override val connection = connectionFlow
    override suspend fun ranking(industry: Boolean, sort: String) = listOf(taxonomy.copy(taxonomyType = if (industry) "INDUSTRY" else "THEME"))
    override fun subscribe() = Unit
}

@RunWith(RobolectricTestRunner::class) @Config(sdk = [35])
class IndustryRealtimeComposeTest {
    @get:Rule val compose = createComposeRule()
    @Test fun rankingComponentsAndModesAreVisible() {
        compose.setContent { IndustryRealtimePanel(IndustryRealtimeUiState.Content(listOf(taxonomy), true, false), {}) }
        compose.onNodeWithTag("realtime-strength-panel").assertIsDisplayed()
    }
}
