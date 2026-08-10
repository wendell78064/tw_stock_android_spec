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
    @Test fun securityInstitutionalTabRenders() {
        compose.setContent { SecurityInstitutionalScreen(SecuritySpotUiState.Empty, 20, {}) }
        compose.onNodeWithTag("security-institutional").assertIsDisplayed()
    }

    @Test fun securityCreditTabRenders() {
        compose.setContent { SecurityCreditScreen(SecuritySpotUiState.Empty) }
        compose.onNodeWithTag("security-credit").assertIsDisplayed()
    }
}
