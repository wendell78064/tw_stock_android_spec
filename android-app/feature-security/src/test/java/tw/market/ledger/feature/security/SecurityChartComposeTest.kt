package tw.market.ledger.feature.security

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.security.presentation.SecurityChartScreen
import tw.market.ledger.feature.security.presentation.SecurityChartUiState
import tw.market.ledger.model.Candle
import tw.market.ledger.model.ChartRange
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.PriceBasis

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class SecurityChartComposeTest {
    @get:Rule val composeRule = createComposeRule()
    private val candle = Candle("2026-08-07T00:00:00+08:00", "40", "42", "39", "41", 1000, null)

    @Test fun candlestickAndSelectedOhlcvAreRendered() {
        composeRule.setContent {
            SecurityChartScreen(
                SecurityChartUiState.Content(listOf(candle), emptyList(), "2026-08-07", DataStatus.FINAL, false, false, "日 K"),
                ChartRange.ONE_DAY, PriceBasis.RAW, emptySet(), candle, {}, {}, {}, {},
            )
        }
        composeRule.onNodeWithTag("candlestick-chart").assertIsDisplayed()
        composeRule.onNodeWithText("2026-08-07T00:00:00+08:00 O 40 H 42 L 39 C 41 V 1000").assertExists()
        composeRule.onNodeWithText("實際歷史成交價 · FINAL").assertIsDisplayed()
    }
}
