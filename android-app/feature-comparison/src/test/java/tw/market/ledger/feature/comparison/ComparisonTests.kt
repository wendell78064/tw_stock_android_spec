package tw.market.ledger.feature.comparison

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import retrofit2.Response
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.network.ComparisonApi
import tw.market.ledger.network.ComparisonEnvelopeDto
import tw.market.ledger.network.ComparisonResultDto
import tw.market.ledger.network.ComparisonSecuritySummaryDto
import tw.market.ledger.network.MetaDto
import tw.market.ledger.network.NormalizedPointDto
import tw.market.ledger.network.ObjectiveSignalDto
import tw.market.ledger.network.RunComparisonInputDto

class FakeComparisonApi : ComparisonApi {
    override suspend fun runComparison(input: RunComparisonInputDto): Response<ComparisonEnvelopeDto> {
        val meta = MetaDto("2026-08-11T00:00:00Z", "2026-08-11T00:00:00Z", "FINAL", "TEST")
        val s1 = ComparisonSecuritySummaryDto(
            security_id = "sec1",
            code = "2330",
            name = "台積電",
            market = "TWSE",
            latest_close = "950.00",
            return_20d = "12.50",
            rsi14 = "65.00",
            data_status = "FINAL"
        )
        val s2 = ComparisonSecuritySummaryDto(
            security_id = "sec2",
            code = "2317",
            name = "鴻海",
            market = "TWSE",
            latest_close = "200.00",
            return_20d = "4.20",
            rsi14 = "48.00",
            data_status = "FINAL"
        )
        val norm = listOf(
            NormalizedPointDto("2026-08-10", mapOf("2330" to "100.00", "2317" to "100.00")),
            NormalizedPointDto("2026-08-11", mapOf("2330" to "102.50", "2317" to "101.00"))
        )
        val sig = listOf(
            ObjectiveSignalDto(
                signal_type = "PRICE_OUTPERFORMANCE",
                subject_code = "2330",
                comparator_code = "2317",
                headline = "台積電 近期報酬表現優於 鴻海",
                details = "2330 報酬率為 12.50%，較 2317 (4.20%) 高出 8.30 個百分點"
            )
        )
        val res = ComparisonResultDto(
            window = input.window,
            requested_start = "2026-07-11",
            effective_start = "2026-08-10",
            effective_end = "2026-08-11",
            securities = listOf(s1, s2),
            normalized_series = norm,
            objective_signals = sig,
            coverage = "1.00"
        )
        return Response.success(ComparisonEnvelopeDto(res, meta))
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ComparisonTests {
    @get:Rule val composeTestRule = createComposeRule()

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var fakeApi: FakeComparisonApi

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        fakeApi = FakeComparisonApi()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testSelectionManagerLimitsAndDuplicates() {
        val manager = ComparisonSelectionManager()
        val s1 = SecurityTarget("2330", MarketCode.TWSE)
        val s2 = SecurityTarget("2317", MarketCode.TWSE)
        val s3 = SecurityTarget("2454", MarketCode.TWSE)
        val s4 = SecurityTarget("2308", MarketCode.TWSE)
        val s5 = SecurityTarget("2382", MarketCode.TWSE)
        val s6 = SecurityTarget("2303", MarketCode.TWSE)

        assertTrue(manager.addTarget(s1))
        assertFalse(manager.addTarget(s1)) // Duplicate
        assertTrue(manager.addTarget(s2))
        assertTrue(manager.addTarget(s3))
        assertTrue(manager.addTarget(s4))
        assertTrue(manager.addTarget(s5))
        assertFalse(manager.addTarget(s6)) // Exceed 5

        assertEquals(5, manager.targets.value.size)
        manager.removeTarget("2330", MarketCode.TWSE)
        assertEquals(4, manager.targets.value.size)
    }

    @Test
    fun testViewModelComparisonFlow() = runTest {
        val vm = ComparisonViewModel(fakeApi)
        val t1 = SecurityTarget("2330", MarketCode.TWSE)
        val t2 = SecurityTarget("2317", MarketCode.TWSE)
        vm.setTargets(listOf(t1, t2))
        testDispatcher.scheduler.advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals(2, state.summaries.size)
        assertEquals("2330", state.summaries[0].code)
        assertEquals(1, state.signals.size)
        assertEquals("台積電 近期報酬表現優於 鴻海", state.signals[0].headline)
    }

    @Test
    fun testComparisonScreenComposeRender() {
        val vm = ComparisonViewModel(fakeApi)
        val t1 = SecurityTarget("2330", MarketCode.TWSE)
        val t2 = SecurityTarget("2317", MarketCode.TWSE)
        vm.setTargets(listOf(t1, t2))

        composeTestRule.setContent {
            ComparisonScreen(viewModel = vm, onNavigateBack = {})
        }
        testDispatcher.scheduler.advanceUntilIdle()
        composeTestRule.waitForIdle()

        composeTestRule.onNodeWithTag("comparison_screen").assertIsDisplayed()
        composeTestRule.onNodeWithTag("normalized_canvas_chart").assertIsDisplayed()
        composeTestRule.onNodeWithTag("sec_summary_2330").assertIsDisplayed()
    }
}
