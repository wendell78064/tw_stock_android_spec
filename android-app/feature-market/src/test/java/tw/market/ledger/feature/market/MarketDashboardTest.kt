package tw.market.ledger.feature.market

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.performScrollToNode
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.market.presentation.MarketDashboardScreen
import tw.market.ledger.feature.market.presentation.MarketDashboardUiState
import tw.market.ledger.model.*

@RunWith(RobolectricTestRunner::class) @Config(sdk=[35])
class MarketDashboardTest {
    @get:Rule val compose = createComposeRule()
    private val index = MarketIndex("TAIEX", "加權指數", MarketCode.TWSE, "2026-08-07",
        "22000", "22100", "21900", "22050", "50", "0.23", "320000000000", 1,
        "2026-08-07T00:00:00Z", DataStatus.FINAL)
    private val breadth = MarketBreadth(MarketCode.TWSE, "2026-08-07", 500, 350, 100, 25, 8,
        950, "320000000000", "2026-08-07T00:00:00Z", DataStatus.FINAL)
    private val overview = MarketOverview(listOf(index), listOf(breadth), emptyList(), emptyList(),
        emptyList(), index.asOf, DataStatus.FINAL)

    @Test fun indexBreadthAndPartialAreVisible() {
        compose.setContent { MarketDashboardScreen(MarketDashboardUiState.Partial(overview.copy(dataStatus=DataStatus.PARTIAL)), 5) }
        compose.onNodeWithTag("index-TAIEX").assertIsDisplayed()
        compose.onNodeWithText("上漲 500　下跌 350　平盤 100").assertIsDisplayed()
        compose.onNodeWithText("Partial：部分盤後資料尚未公布").assertIsDisplayed()
    }
    @Test fun offlineAndEmptyNeverRenderBlank() {
        compose.setContent { MarketDashboardScreen(MarketDashboardUiState.Offline(overview.copy(fromCache=true)), 1) }
        compose.onNodeWithText("Offline / Stale：顯示 ${overview.asOf} 快取").assertIsDisplayed()
    }
    @Test fun unavailableLendingAndVixNeverRenderAsZero() {
        val lending = LendingPoint("2026-08-07", 1234, null, null, index.asOf, DataStatus.PARTIAL)
        compose.setContent { MarketDashboardScreen(
            MarketDashboardUiState.Partial(overview.copy(indexes=emptyList(), breadth=emptyList(),
                lending=listOf(lending), dataStatus=DataStatus.PARTIAL)), 1) }
        compose.onNodeWithText("VIX：正式資料來源目前不可用").assertIsDisplayed()
        compose.onNodeWithTag("market-dashboard").performScrollToNode(
            hasText("借券餘額：官方自動化資料來源目前未提供"))
        compose.onNodeWithText("借券餘額：官方自動化資料來源目前未提供").assertIsDisplayed()
    }
}
