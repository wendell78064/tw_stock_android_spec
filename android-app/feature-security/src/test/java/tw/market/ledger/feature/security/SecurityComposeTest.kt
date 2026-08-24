package tw.market.ledger.feature.security

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.security.presentation.SecurityDetailScreen
import tw.market.ledger.feature.security.presentation.SecurityDetailUiState
import tw.market.ledger.feature.security.presentation.SecuritySearchScreen
import tw.market.ledger.feature.security.presentation.SecuritySearchUiState
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeQuote

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class SecurityComposeTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun searchResultIsRendered() {
        val item = security()
        composeRule.setContent {
            SecuritySearchScreen(
                query = "測試",
                state = SecuritySearchUiState.Success(listOf(item), item.asOf),
                onQueryChange = {}, onClear = {}, onSearch = {}, onSecurityClick = {},
            )
        }
        composeRule.onNodeWithText("1234 測試科技").assertIsDisplayed()
        composeRule.onNodeWithText("資料狀態：FINAL").assertIsDisplayed()
    }

    @Test fun detailRendersScopeBoundary() {
        composeRule.setContent {
            SecurityDetailScreen(SecurityDetailUiState.Success(security()))
        }
        composeRule.onNodeWithText("1234 測試科技").assertIsDisplayed()
        composeRule.onNodeWithText("主要產業：測試科技業").assertIsDisplayed()
    }

    @Test fun realtimeMissingChangeDoesNotRenderAsZero() {
        val quote = RealtimeQuote(
            securityId = "sec_1234",
            marketId = "TWSE",
            code = "1234",
            exchangeTimestamp = "2026-08-24T03:00:00Z",
            receivedAt = "2026-08-24T03:00:00.100Z",
            lastPrice = "100.0",
            changePercent = null,
            dataStatus = RealtimeDataStatus.STALE,
        )
        composeRule.setContent {
            SecurityDetailScreen(SecurityDetailUiState.Success(security()), quote)
        }
        composeRule.onNodeWithText("即時價格: \$100.0 (--%)").assertIsDisplayed()
        composeRule.onNodeWithText("[STALE]").assertIsDisplayed()
    }
}
