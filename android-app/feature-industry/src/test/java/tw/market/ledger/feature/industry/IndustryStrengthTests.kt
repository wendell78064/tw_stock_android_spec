package tw.market.ledger.feature.industry

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
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
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.industry.domain.IndustryRepository
import tw.market.ledger.feature.industry.presentation.StrengthDetailScreen
import tw.market.ledger.feature.industry.presentation.StrengthDetailUiState
import tw.market.ledger.feature.industry.presentation.StrengthDetailViewModel
import tw.market.ledger.feature.industry.presentation.StrengthRankingScreen
import tw.market.ledger.feature.industry.presentation.StrengthRankingUiState
import tw.market.ledger.feature.industry.presentation.StrengthRankingViewModel
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.Industry
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.StrengthComponents
import tw.market.ledger.model.TaxonomyDetail
import tw.market.ledger.model.TaxonomyLeader
import tw.market.ledger.model.TaxonomyStrength
import tw.market.ledger.model.TaxonomyStrengthDetail
import tw.market.ledger.model.Theme
import tw.market.ledger.network.RealtimeQuoteType
import tw.market.ledger.network.RealtimeSubscriptionClient
import tw.market.ledger.network.RealtimeSubscriptionManager

private val SAMPLE_STRENGTH = TaxonomyStrength(
    id = "str_1",
    taxonomyId = "ind_1",
    taxonomyCode = "24",
    taxonomyName = "半導體",
    taxonomyType = "OFFICIAL",
    tradeDate = "2026-08-11",
    window = 20,
    equalWeightReturn = "4.50",
    marketCapWeightedReturn = null,
    totalMembers = 10,
    validMembers = 10,
    coverageRatio = "1.0000",
    advancers = 7,
    decliners = 2,
    unchanged = 1,
    advanceRatio = "0.7000",
    aboveMa20Pct = "0.8000",
    aboveMa60Pct = "0.6000",
    foreignNetAmount = "5000000",
    investmentTrustNetAmount = "1000000",
    dealerNetAmount = "500000",
    marginBalanceChange = "200000",
    shortBalanceChange = "10000",
    lendingBalanceChange = null,
    turnoverAmount = "5000000000",
    turnoverShare = null,
    turnoverMomentum = "1.2000",
    components = StrengthComponents(
        momentumScore = "85.00",
        breadthScore = "75.00",
        technicalScore = "70.00",
        institutionalScore = "80.00",
        turnoverScore = "60.00",
    ),
    strengthScore = "78.50",
    componentCoverage = "1.0000",
    rank = 1,
    algorithmVersion = "twml-industry-strength-v1",
    dataStatus = DataStatus.FINAL,
    asOf = "2026-08-11T00:00:00Z",
)

private val SAMPLE_LEADER = TaxonomyLeader(
    securityId = "sec_1",
    code = "2330",
    name = "台積電",
    market = MarketCode.TWSE,
    returnPct = "5.25",
    latestClose = "1000.0",
    foreignNet = "5000000",
    dataStatus = DataStatus.FINAL,
)

private val SAMPLE_LAGGARD = TaxonomyLeader(
    securityId = "sec_2",
    code = "2303",
    name = "聯電",
    market = MarketCode.TWSE,
    returnPct = "-1.20",
    latestClose = "50.0",
    foreignNet = "-1000000",
    dataStatus = DataStatus.FINAL,
)

private class FakeStrengthRepository : IndustryRepository {
    var strengthsResult: Result<Pair<List<TaxonomyStrength>, Boolean>> = Result.success(Pair(listOf(SAMPLE_STRENGTH), false))
    var detailResult: Result<TaxonomyStrengthDetail> = Result.success(
        TaxonomyStrengthDetail(
            snapshot = SAMPLE_STRENGTH,
            leaders = listOf(SAMPLE_LEADER),
            laggards = listOf(SAMPLE_LAGGARD),
            isStale = false,
        )
    )

    override suspend fun getIndustries() = Result.success(Pair(emptyList<Industry>(), false))
    override suspend fun getIndustryDetail(id: String) = Result.failure<TaxonomyDetail<Industry>>(Exception("unused"))
    override suspend fun getThemes() = Result.success(Pair(emptyList<Theme>(), false))
    override suspend fun getThemeDetail(id: String) = Result.failure<TaxonomyDetail<Theme>>(Exception("unused"))
    override suspend fun getIndustryStrengths(window: Int, sort: String) = strengthsResult
    override suspend fun getThemeStrengths(window: Int, sort: String) = strengthsResult
    override suspend fun getTaxonomyStrengthDetail(id: String, isIndustry: Boolean, window: Int) = detailResult
    override suspend fun getTaxonomyStrengthHistory(id: String, isIndustry: Boolean, window: Int, limit: Int) = strengthsResult
}

@OptIn(ExperimentalCoroutinesApi::class)
class IndustryStrengthViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun before() = Dispatchers.setMain(dispatcher)

    @After
    fun after() = Dispatchers.resetMain()

    @Test
    fun `strength ranking viewmodel loads strengths`() = runTest(dispatcher) {
        val repo = FakeStrengthRepository()
        val vm = StrengthRankingViewModel(repo)
        dispatcher.scheduler.advanceUntilIdle()

        val state = vm.uiState.value
        assertTrue(state is StrengthRankingUiState.Success)
        val success = state as StrengthRankingUiState.Success
        assertEquals(1, success.strengths.size)
        assertEquals("78.50", success.strengths[0].strengthScore)
    }

    @Test
    fun `strength detail viewmodel loads detail and leaders`() = runTest(dispatcher) {
        val repo = FakeStrengthRepository()
        val client = FakeRealtimeClient()
        val manager = RealtimeSubscriptionManager(client, scope = backgroundScope, industryRealtimeEnabled = true)
        val vm = StrengthDetailViewModel(repo, manager)
        vm.load("ind_1", isIndustryTaxonomy = true, window = 20)
        dispatcher.scheduler.advanceUntilIdle()

        val state = vm.uiState.value
        assertTrue(state is StrengthDetailUiState.Success)
        val success = state as StrengthDetailUiState.Success
        assertEquals("78.50", success.detail.snapshot.strengthScore)
        assertEquals(1, success.detail.leaders.size)
        assertEquals("2330", success.detail.leaders[0].code)
    }

    @Test
    fun `strength detail viewmodel manages p3 realtime lifecycle and set-diff`() = runTest(dispatcher) {
        val repo = FakeStrengthRepository()
        val client = FakeRealtimeClient()
        val managerScope = kotlinx.coroutines.CoroutineScope(dispatcher + kotlinx.coroutines.Job())
        val manager = RealtimeSubscriptionManager(client, scope = managerScope, industryRealtimeEnabled = true)
        val store = androidx.lifecycle.ViewModelStore()
        val vm = StrengthDetailViewModel(repo, manager)
        store.put("detail", vm)

        // 1. Initial load before activation -> no subscriptions
        vm.load("ind_1", isIndustryTaxonomy = true, window = 20)
        dispatcher.scheduler.advanceUntilIdle()
        assertTrue(client.calls.isEmpty())

        // 2. Entering detail screen activates realtime -> acquires leaders + laggards
        vm.activateRealtime()
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(
            listOf(
                FakeRealtimeClient.Call("subscribe", "TWSE", "2303", setOf(RealtimeQuoteType.TICK)),
                FakeRealtimeClient.Call("subscribe", "TWSE", "2330", setOf(RealtimeQuoteType.TICK)),
            ),
            client.calls.sortedBy { it.code }
        )

        // 3. Emitting realtime quote updates leader row overlay
        client.emit(
            tw.market.ledger.model.RealtimeQuote(
                securityId = "sec_1",
                marketId = "TWSE",
                code = "2330",
                exchangeTimestamp = "2026-09-04T09:30:00Z",
                receivedAt = "2026-09-04T09:30:01Z",
                lastPrice = "1050.0",
                change = "50.0",
                changePercent = "5.00",
                dataStatus = tw.market.ledger.model.RealtimeDataStatus.LIVE,
            )
        )
        dispatcher.scheduler.advanceUntilIdle()
        val updatedState = vm.uiState.value as StrengthDetailUiState.Success
        val leader2330 = updatedState.detail.leaders.first { it.code == "2330" }
        assertEquals("1050.0", leader2330.latestClose)
        assertEquals("5.00", leader2330.returnPct)
        assertEquals(DataStatus.LIVE, leader2330.dataStatus)

        // 4. Same membership reorder / reload causes no subscription churn
        client.calls.clear()
        repo.detailResult = Result.success(
            TaxonomyStrengthDetail(
                snapshot = SAMPLE_STRENGTH,
                leaders = listOf(SAMPLE_LAGGARD), // reordered
                laggards = listOf(SAMPLE_LEADER),
                isStale = false,
            )
        )
        vm.load("ind_1", isIndustryTaxonomy = true, window = 20)
        dispatcher.scheduler.advanceUntilIdle()
        assertTrue(client.calls.isEmpty()) // No churn on identical union set

        // 5. Switching taxonomy performs set-diff
        client.calls.clear()
        val leaderNew = TaxonomyLeader(
            securityId = "sec_3",
            code = "2454",
            name = "聯發科",
            market = MarketCode.TWSE,
            returnPct = "3.00",
            latestClose = "1200.0",
            dataStatus = DataStatus.FINAL,
        )
        repo.detailResult = Result.success(
            TaxonomyStrengthDetail(
                snapshot = SAMPLE_STRENGTH,
                leaders = listOf(leaderNew),
                laggards = listOf(SAMPLE_LEADER), // 2330 retained, 2303 removed
                isStale = false,
            )
        )
        vm.load("ind_2", isIndustryTaxonomy = true, window = 20)
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(
            listOf(FakeRealtimeClient.Call("unsubscribe", "TWSE", "2303", setOf(RealtimeQuoteType.TICK))),
            client.calls.filter { it.action == "unsubscribe" }
        )
        assertEquals(
            listOf(FakeRealtimeClient.Call("subscribe", "TWSE", "2454", setOf(RealtimeQuoteType.TICK))),
            client.calls.filter { it.action == "subscribe" }
        )

        // 6. Leaving screen / clearing ViewModelStore releases all P3 ownership
        client.calls.clear()
        store.clear()
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(
            listOf(
                FakeRealtimeClient.Call("unsubscribe", "TWSE", "2330", setOf(RealtimeQuoteType.TICK)),
                FakeRealtimeClient.Call("unsubscribe", "TWSE", "2454", setOf(RealtimeQuoteType.TICK)),
            ),
            client.calls.sortedBy { it.code }
        )
    }
}

private class FakeRealtimeClient : RealtimeSubscriptionClient {
    data class Call(val action: String, val market: String, val code: String, val quoteTypes: Set<RealtimeQuoteType>)
    private val mutableQuotes = kotlinx.coroutines.flow.MutableSharedFlow<tw.market.ledger.model.RealtimeQuote>(replay = 1)
    override val quotesFlow: kotlinx.coroutines.flow.SharedFlow<tw.market.ledger.model.RealtimeQuote> = mutableQuotes
    val calls = mutableListOf<Call>()
    override fun connect() = Unit
    override fun subscribe(market: String, code: String, quoteTypes: Set<RealtimeQuoteType>) {
        calls += Call("subscribe", market, code, quoteTypes)
    }
    override fun unsubscribe(market: String, code: String, quoteTypes: Set<RealtimeQuoteType>) {
        calls += Call("unsubscribe", market, code, quoteTypes)
    }
    fun emit(quote: tw.market.ledger.model.RealtimeQuote) = mutableQuotes.tryEmit(quote)
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class IndustryStrengthComposeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun `strength ranking screen renders items and chips`() {
        var selectedWindow: Int? = null
        compose.setContent {
            StrengthRankingScreen(
                uiState = StrengthRankingUiState.Success(
                    strengths = listOf(SAMPLE_STRENGTH),
                    window = 20,
                    sort = "strength",
                    isIndustry = true,
                ),
                onWindowSelect = { selectedWindow = it },
                onSortSelect = {},
                onTabSelect = {},
                onTaxonomyClick = { _, _ -> },
                onRetry = {},
            )
        }

        compose.onNodeWithText("產業與題材強弱排行").assertIsDisplayed()
        compose.onNodeWithText("半導體 (24)").assertIsDisplayed()
        compose.onNodeWithText("78.50").assertIsDisplayed()
        compose.onNodeWithTag("chip_window_5").performClick()
        assertEquals(5, selectedWindow)
    }

    @Test
    fun `strength detail screen renders breakdown and leaders`() {
        var clickedSec: String? = null
        compose.setContent {
            StrengthDetailScreen(
                uiState = StrengthDetailUiState.Success(
                    detail = TaxonomyStrengthDetail(
                        snapshot = SAMPLE_STRENGTH,
                        leaders = listOf(SAMPLE_LEADER),
                        laggards = listOf(SAMPLE_LAGGARD),
                    ),
                    history = listOf(SAMPLE_STRENGTH),
                    window = 20,
                ),
                onWindowSelect = {},
                onSecurityClick = { market, code -> clickedSec = "$market:$code" },
                onRetry = {},
            )
        }

        compose.onNodeWithText("半導體 (24) - 強度明細").assertIsDisplayed()
        compose.onNodeWithText("5大成分分數拆解").assertIsDisplayed()
        compose.onNodeWithText("動能 (30%)").assertIsDisplayed()
        compose.onNodeWithText("85.00").assertIsDisplayed()
        compose.onNodeWithTag("strength_detail_lazy_column").performScrollToNode(hasTestTag("leader_item_2330"))
        compose.onNodeWithTag("leader_item_2330").performClick()
        assertEquals("TWSE:2330", clickedSec)
    }
}
