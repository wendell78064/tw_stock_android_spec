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
        val vm = StrengthDetailViewModel(repo)
        vm.load("ind_1", isIndustryTaxonomy = true, window = 20)
        dispatcher.scheduler.advanceUntilIdle()

        val state = vm.uiState.value
        assertTrue(state is StrengthDetailUiState.Success)
        val success = state as StrengthDetailUiState.Success
        assertEquals("78.50", success.detail.snapshot.strengthScore)
        assertEquals(1, success.detail.leaders.size)
        assertEquals("2330", success.detail.leaders[0].code)
    }
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
