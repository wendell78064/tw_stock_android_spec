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
}

