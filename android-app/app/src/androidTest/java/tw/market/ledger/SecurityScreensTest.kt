package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.security.presentation.SecurityDetailScreen
import tw.market.ledger.feature.security.presentation.SecurityDetailUiState
import tw.market.ledger.feature.security.presentation.SecuritySearchScreen
import tw.market.ledger.feature.security.presentation.SecuritySearchUiState
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security
import tw.market.ledger.model.SecurityStatus
import tw.market.ledger.model.SecurityType

class SecurityScreensTest {
    @get:Rule val composeRule = createComposeRule()
    private val security = Security(
        "id", "1234", "測試科技", MarketCode.TWSE, SecurityType.COMMON_STOCK,
        SecurityStatus.ACTIVE, "測試科技業", "2023-01-02", true,
        "2026-08-06T00:00:00Z", "2026-08-06T00:00:01Z", DataStatus.FINAL,
    )

    @Test fun searchResultHappyPathIsVisible() {
        var opened: Security? = null
        composeRule.setContent {
            SecuritySearchScreen("測試", SecuritySearchUiState.Success(listOf(security), security.asOf), {}, {}, {}, { opened = it })
        }
        composeRule.onNodeWithText("1234 測試科技").assertIsDisplayed()
        composeRule.onNodeWithText("資料狀態：FINAL").assertIsDisplayed()
        composeRule.onNodeWithText("1234 測試科技").performClick()
        assertEquals(security, opened)
    }

    @Test fun basicDetailExplicitlyExcludesLaterFeatures() {
        composeRule.setContent { SecurityDetailScreen(SecurityDetailUiState.Success(security)) }
        composeRule.onNodeWithText("1234 測試科技").assertIsDisplayed()
        composeRule.onNodeWithText("主要產業：測試科技業").assertIsDisplayed()
    }
}
