package tw.market.ledger.feature.security

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.security.presentation.*
import tw.market.ledger.model.*

@RunWith(RobolectricTestRunner::class) @Config(sdk=[35])
class SecuritySpotComposeTest {
    @get:Rule val compose = createComposeRule()
    @Test fun institutionalTabRenders() {
        val point = InstitutionalPoint(MarketCode.TWSE, "1234", "2026-08-07", InstitutionType.FOREIGN,
            null, "120000", "100000", "20000", "400000", 3, "2026-08-07", DataStatus.FINAL)
        compose.setContent { SecurityInstitutionalScreen(SecuritySpotUiState.Institutional(listOf(point)), 20, {}) }
        compose.onNodeWithTag("security-institutional").assertIsDisplayed()
    }

    @Test fun creditTabRenders() {
        val margin = MarginPoint("2026-08-07", 1000, 10, 100, 2, "10", "2026-08-07", DataStatus.FINAL)
        compose.setContent { SecurityCreditScreen(SecuritySpotUiState.Credit(SecurityCredit(listOf(margin), emptyList()))) }
        compose.onNodeWithTag("security-credit").assertIsDisplayed()
    }
}
