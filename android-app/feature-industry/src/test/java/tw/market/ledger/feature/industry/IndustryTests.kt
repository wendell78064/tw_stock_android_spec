package tw.market.ledger.feature.industry

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.lifecycle.SavedStateHandle
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
import tw.market.ledger.feature.industry.presentation.IndustryDetailScreen
import tw.market.ledger.feature.industry.presentation.IndustryDetailUiState
import tw.market.ledger.feature.industry.presentation.IndustryDetailViewModel
import tw.market.ledger.feature.industry.presentation.IndustryLandingScreen
import tw.market.ledger.feature.industry.presentation.IndustryLandingUiState
import tw.market.ledger.feature.industry.presentation.IndustryLandingViewModel
import tw.market.ledger.feature.industry.presentation.ThemeDetailScreen
import tw.market.ledger.feature.industry.presentation.ThemeDetailUiState
import tw.market.ledger.feature.industry.presentation.ThemeDetailViewModel
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.Industry
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.TaxonomyDetail
import tw.market.ledger.model.TaxonomyMember
import tw.market.ledger.model.Theme

private val SAMPLE_INDUSTRY = Industry("ind_1", "24", "半導體", "TWSE", 1)
private val SAMPLE_THEME = Theme("t_1", "AI_SERVER", "AI 伺服器", "AI supply chain", "CUSTOM", 1)
private val SAMPLE_MEMBER = TaxonomyMember(
    securityId = "sec_1",
    code = "2330",
    name = "台積電",
    market = MarketCode.TWSE,
    close = "1000.0",
    change = "20.0",
    changePercent = "2.04",
    asOf = "2026-08-11T00:00:00Z",
    dataStatus = DataStatus.FINAL,
)

private class FakeIndustryRepository : IndustryRepository {
    var industriesResult: Result<Pair<List<Industry>, Boolean>> = Result.success(Pair(listOf(SAMPLE_INDUSTRY), false))
    var themesResult: Result<Pair<List<Theme>, Boolean>> = Result.success(Pair(listOf(SAMPLE_THEME), false))
    var indDetailResult: Result<TaxonomyDetail<Industry>> = Result.success(
        TaxonomyDetail(
            taxonomy = SAMPLE_INDUSTRY,
            members = listOf(SAMPLE_MEMBER),
            asOf = "2026-08-11T00:00:00Z",
            dataStatus = DataStatus.FINAL,
            isStale = false,
        )
    )
    var themeDetailResult: Result<TaxonomyDetail<Theme>> = Result.success(
        TaxonomyDetail(
            taxonomy = SAMPLE_THEME,
            members = listOf(SAMPLE_MEMBER),
            asOf = "2026-08-11T00:00:00Z",
            dataStatus = DataStatus.FINAL,
            isStale = false,
        )
    )

    override suspend fun getIndustries() = industriesResult
    override suspend fun getIndustryDetail(id: String) = indDetailResult
    override suspend fun getThemes() = themesResult
    override suspend fun getThemeDetail(id: String) = themeDetailResult
}

@OptIn(ExperimentalCoroutinesApi::class)
class IndustryViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun before() = Dispatchers.setMain(dispatcher)

    @After
    fun after() = Dispatchers.resetMain()

    @Test
    fun `landing viewmodel loads industries and themes`() = runTest(dispatcher) {
        val repo = FakeIndustryRepository()
        val vm = IndustryLandingViewModel(repo)
        dispatcher.scheduler.advanceUntilIdle()

        val state = vm.uiState.value
        assertTrue(state is IndustryLandingUiState.Success)
        val success = state as IndustryLandingUiState.Success
        assertEquals(1, success.industries.size)
        assertEquals("半導體", success.industries[0].name)
        assertEquals(1, success.themes.size)
        assertEquals("AI 伺服器", success.themes[0].name)
    }

    @Test
    fun `industry detail viewmodel loads detail`() = runTest(dispatcher) {
        val repo = FakeIndustryRepository()
        val savedState = SavedStateHandle(mapOf("id" to "ind_1"))
        val vm = IndustryDetailViewModel(repo, savedState)
        dispatcher.scheduler.advanceUntilIdle()

        val state = vm.uiState.value
        assertTrue(state is IndustryDetailUiState.Success)
        val detail = (state as IndustryDetailUiState.Success).detail
        assertEquals("半導體", detail.taxonomy.name)
        assertEquals(1, detail.members.size)
        assertEquals("2330", detail.members[0].code)
    }

    @Test
    fun `theme detail viewmodel loads detail`() = runTest(dispatcher) {
        val repo = FakeIndustryRepository()
        val savedState = SavedStateHandle(mapOf("id" to "t_1"))
        val vm = ThemeDetailViewModel(repo, savedState)
        dispatcher.scheduler.advanceUntilIdle()

        val state = vm.uiState.value
        assertTrue(state is ThemeDetailUiState.Success)
        val detail = (state as ThemeDetailUiState.Success).detail
        assertEquals("AI 伺服器", detail.taxonomy.name)
        assertEquals(1, detail.members.size)
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class IndustryComposeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun `industry landing renders official industry items and tab switching`() {
        var clickedInd: String? = null
        var clickedTheme: String? = null

        compose.setContent {
            IndustryLandingScreen(
                uiState = IndustryLandingUiState.Success(
                    industries = listOf(SAMPLE_INDUSTRY),
                    themes = listOf(SAMPLE_THEME),
                ),
                onIndustryClick = { clickedInd = it },
                onThemeClick = { clickedTheme = it },
                onRetry = {},
            )
        }

        compose.onNodeWithText("半導體").assertIsDisplayed()
        compose.onNodeWithTag("industry_item_24").performClick()
        assertEquals("ind_1", clickedInd)

        compose.onNodeWithTag("tab_custom_theme").performClick()
        compose.onNodeWithText("AI 伺服器").assertIsDisplayed()
        compose.onNodeWithTag("theme_item_AI_SERVER").performClick()
        assertEquals("t_1", clickedTheme)
    }

    @Test
    fun `industry detail screen renders taxonomy header and stock members`() {
        var clickedSec: String? = null

        compose.setContent {
            IndustryDetailScreen(
                uiState = IndustryDetailUiState.Success(
                    detail = TaxonomyDetail(
                        taxonomy = SAMPLE_INDUSTRY,
                        members = listOf(SAMPLE_MEMBER),
                        asOf = "2026-08-11T00:00:00Z",
                        dataStatus = DataStatus.FINAL,
                        isStale = false,
                    )
                ),
                onSecurityClick = { market, code -> clickedSec = "$market:$code" },
                onRetry = {},
            )
        }

        compose.onNodeWithText("半導體").assertIsDisplayed()
        compose.onNodeWithText("台積電 (2330)").assertIsDisplayed()
        compose.onNodeWithText("1000.0").assertIsDisplayed()
        compose.onNodeWithTag("member_item_2330").performClick()
        assertEquals("TWSE:2330", clickedSec)
    }

    @Test
    fun `theme detail screen renders stale badge when offline`() {
        compose.setContent {
            ThemeDetailScreen(
                uiState = ThemeDetailUiState.Success(
                    detail = TaxonomyDetail(
                        taxonomy = SAMPLE_THEME,
                        members = listOf(SAMPLE_MEMBER.copy(dataStatus = DataStatus.STALE)),
                        asOf = "2026-08-11T00:00:00Z",
                        dataStatus = DataStatus.STALE,
                        isStale = true,
                    )
                ),
                onSecurityClick = { _, _ -> },
                onRetry = {},
            )
        }

        compose.onNodeWithText("AI 伺服器").assertIsDisplayed()
        compose.onNodeWithText("目前顯示離線快取資料 (STALE)").assertIsDisplayed()
    }
}
