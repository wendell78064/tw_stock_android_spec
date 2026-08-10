package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.market.presentation.*
import tw.market.ledger.feature.security.presentation.*
import tw.market.ledger.model.*

class Phase2MarketInstrumentationTest {
    @get:Rule val compose = createComposeRule()
    private val index = MarketIndex("TAIEX", "加權指數", MarketCode.TWSE, "2026-08-07", "1", "2", "1", "2", "1", "1", "100", 1, "2026-08-07", DataStatus.FINAL)
    @Test fun marketDashboardAndWindowSwitchAreInteractive() {
        var selected = 1
        val otc = index.copy(code="OTC", name="櫃買指數", market=MarketCode.TPEX)
        val overview = MarketOverview(listOf(index, otc), emptyList(), emptyList(), emptyList(), emptyList(), "2026-08-07", DataStatus.FINAL)
        compose.setContent { MarketDashboardScreen(MarketDashboardUiState.Success(overview), selected, onWindow={selected=it}) }
        compose.onNodeWithTag("index-TAIEX").assertIsDisplayed(); compose.onNodeWithTag("index-OTC").assertIsDisplayed()
        compose.onNodeWithText("5日").performClick(); assertEquals(5, selected)
    }
    @Test fun futuresCardNavigates() {
        val product = FuturesProduct("TX", "臺股期貨", "200", "TWD", true)
        val quote = FuturesQuote("TX202608", "202608", "2026-08-07", "23000", "23200",
            "22900", "23100", "23110", "100", "0.43", 1000, 5000, "120",
            DataStatus.FINAL, "2026-08-07T00:00:00Z")
        val futures = FuturesOverview(product, quote, quote.copy(contractCode="TX202609"), DataStatus.FINAL)
        var opened = ""
        val overview = MarketOverview(listOf(index), emptyList(), emptyList(), emptyList(), emptyList(),
            "2026-08-07", DataStatus.FINAL)
        compose.setContent { MarketDashboardScreen(MarketDashboardUiState.Success(overview), 1,
            futures=futures, onFuturesClick={opened=it}) }
        compose.onNodeWithTag("futures-card-TX").performClick(); assertEquals("TX", opened)
    }

    @Test fun futuresDetailChangesRangeAndRollMethod() {
        val product = FuturesProduct("TX", "臺股期貨", "200", "TWD", true)
        val quote = FuturesQuote("TX202608", "202608", "2026-08-07", "23000", "23200",
            "22900", "23100", "23110", "100", "0.43", 1000, 5000, "120",
            DataStatus.FINAL, "2026-08-07T00:00:00Z")
        val futures = FuturesOverview(product, quote, quote.copy(contractCode="TX202609"), DataStatus.FINAL)
        var range = FuturesRange.D30; var roll = RollMethod.OPEN_INTEREST
        compose.setContent { FuturesDetailScreen("TX", FuturesDetailUiState.Loaded(futures,
            emptyList(), emptyList()), range, roll, { range=it }, { roll=it }) }
        compose.onNodeWithTag("futures-detail").assertIsDisplayed()
        compose.onNodeWithText("D5").performClick(); compose.onNodeWithText("VOLUME").performClick()
        assertEquals(FuturesRange.D5, range); assertEquals(RollMethod.VOLUME, roll)
    }
    @Test fun securityInstitutionalTabRenders() {
        compose.setContent { SecurityInstitutionalScreen(SecuritySpotUiState.Empty, 20, {}) }
        compose.onNodeWithTag("security-institutional").assertIsDisplayed()
    }

    @Test fun securityCreditTabRenders() {
        compose.setContent { SecurityCreditScreen(SecuritySpotUiState.Empty) }
        compose.onNodeWithTag("security-credit").assertIsDisplayed()
    }
}
