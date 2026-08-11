package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.watchlist.presentation.WatchlistScreen
import tw.market.ledger.feature.watchlist.presentation.WatchlistUiState
import tw.market.ledger.model.Watchlist
import tw.market.ledger.model.WatchlistDashboard
import tw.market.ledger.model.WatchlistItem

class WatchlistInstrumentationTest {
    @get:Rule val compose = createComposeRule()
    @Test fun deterministicWatchlistScenario() {
        val groups = listOf(Watchlist("default", "我的自選", 0), Watchlist("test", "測試自選", 1))
        val items = listOf(
            WatchlistItem("second", "test", "5678", "第二檔", "TWSE", 0, close="20", priceAsOf="2026-08-11", dataStatus="FINAL"),
            WatchlistItem("first", "test", "1234", "測試股票", "TWSE", 1, targetPrice="18", stopPrice="9", addPrice="12", close="15", priceAsOf="2026-08-11", dataStatus="FINAL"),
        )
        compose.setContent { WatchlistScreen(WatchlistUiState.Success(WatchlistDashboard(groups, "test", items), tw.market.ledger.model.WatchlistSort.MANUAL)) }
        compose.onNodeWithText("測試自選").assertIsDisplayed()
        compose.onNodeWithText("5678 第二檔").assertIsDisplayed()
        compose.onNodeWithText("1234 測試股票").assertIsDisplayed()
        compose.onNodeWithText("編輯").assertIsDisplayed()
        compose.onNodeWithText("移出").assertIsDisplayed()
    }
}
