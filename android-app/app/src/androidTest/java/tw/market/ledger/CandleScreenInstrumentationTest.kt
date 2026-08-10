package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.security.presentation.SecurityChartScreen
import tw.market.ledger.feature.security.presentation.SecurityChartUiState
import tw.market.ledger.model.*

class CandleScreenInstrumentationTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun candleRangeBasisOhlcAndIndicatorControlsAreInteractive() {
        val candle = Candle("2026-08-07T00:00:00+08:00", "40", "42", "39", "41", 1000, null)
        var selectedRange = ChartRange.ONE_DAY
        var selectedBasis = PriceBasis.RAW
        var indicator = ""
        composeRule.setContent {
            SecurityChartScreen(SecurityChartUiState.Content(listOf(candle), emptyList(), "2026-08-07",
                DataStatus.FINAL, false, false, null), ChartRange.ONE_DAY, PriceBasis.RAW,
                emptySet(), candle, { selectedRange = it }, { selectedBasis = it }, { indicator = it }, {})
        }
        composeRule.onNodeWithTag("candlestick-chart").assertIsDisplayed()
        composeRule.onNodeWithText("1Y").performClick()
        composeRule.onNodeWithText("ADJUSTED").performClick()
        composeRule.onNodeWithText("RSI14").performClick()
        assertEquals(ChartRange.ONE_YEAR, selectedRange)
        assertEquals(PriceBasis.ADJUSTED, selectedBasis)
        assertEquals("RSI14", indicator)
        composeRule.onNodeWithText("2026-08-07T00:00:00+08:00 O 40 H 42 L 39 C 41 V 1000").assertIsDisplayed()
    }
}
