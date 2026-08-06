package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.market.presentation.FoundationScreen

class FoundationScreenTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun phaseZeroHappyPathShowsApiConnectionTarget() {
        composeRule.setContent { FoundationScreen("http://10.0.2.2:8000/v1/") }
        composeRule.onNodeWithText("基礎架構已就緒").assertIsDisplayed()
        composeRule.onNodeWithText("本機 API：http://10.0.2.2:8000/v1/").assertIsDisplayed()
    }
}

