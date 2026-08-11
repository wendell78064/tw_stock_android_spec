package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.industry.presentation.IndustryDetailScreen
import tw.market.ledger.feature.industry.presentation.IndustryDetailUiState
import tw.market.ledger.feature.industry.presentation.IndustryLandingScreen
import tw.market.ledger.feature.industry.presentation.IndustryLandingUiState
import tw.market.ledger.feature.industry.presentation.ThemeDetailScreen
import tw.market.ledger.feature.industry.presentation.ThemeDetailUiState
import tw.market.ledger.feature.security.presentation.SecurityDetailScreen
import tw.market.ledger.feature.security.presentation.SecurityDetailUiState
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.Industry
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security
import tw.market.ledger.model.SecurityStatus
import tw.market.ledger.model.SecurityType
import tw.market.ledger.model.TaxonomyDetail
import tw.market.ledger.model.TaxonomyMember
import tw.market.ledger.model.Theme
import tw.market.ledger.model.ThemeRef

class IndustryInstrumentationTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun deterministicIndustryAndThemeFlow() {
        val semiIndustry = Industry("ind_24", "24", "半導體", "TWSE", 1)
        val aiTheme = Theme("t_ai", "AI_SERVER", "AI 伺服器", "AI supply chain", "CUSTOM", 1)

        val tsmcMember = TaxonomyMember(
            securityId = "sec_2330",
            code = "2330",
            name = "台積電",
            market = MarketCode.TWSE,
            close = "1000.0",
            change = "20.0",
            changePercent = "2.04",
            asOf = "2026-08-11T00:00:00Z",
            dataStatus = DataStatus.FINAL,
        )

        val quantaMember = TaxonomyMember(
            securityId = "sec_2382",
            code = "2382",
            name = "廣達",
            market = MarketCode.TWSE,
            close = "280.0",
            change = "5.0",
            changePercent = "1.82",
            asOf = "2026-08-11T00:00:00Z",
            dataStatus = DataStatus.FINAL,
        )

        var navSelection: String? = null

        // 1. Landing Screen Navigation
        compose.setContent {
            IndustryLandingScreen(
                uiState = IndustryLandingUiState.Success(
                    industries = listOf(semiIndustry),
                    themes = listOf(aiTheme),
                ),
                onIndustryClick = { navSelection = "industry:$it" },
                onThemeClick = { navSelection = "theme:$it" },
                onRetry = {},
            )
        }

        compose.onNodeWithText("半導體").assertIsDisplayed()
        compose.onNodeWithTag("industry_item_24").performClick()
        assertEquals("industry:ind_24", navSelection)

        compose.onNodeWithTag("tab_custom_theme").performClick()
        compose.onNodeWithText("AI 伺服器").assertIsDisplayed()
        compose.onNodeWithTag("theme_item_AI_SERVER").performClick()
        assertEquals("theme:t_ai", navSelection)

        // 2. Industry Detail Screen: Verify Member
        compose.setContent {
            IndustryDetailScreen(
                uiState = IndustryDetailUiState.Success(
                    detail = TaxonomyDetail(
                        taxonomy = semiIndustry,
                        members = listOf(tsmcMember),
                        asOf = "2026-08-11T00:00:00Z",
                        dataStatus = DataStatus.FINAL,
                    )
                ),
                onSecurityClick = { market, code -> navSelection = "sec:$market:$code" },
                onRetry = {},
            )
        }

        compose.onNodeWithText("台積電 (2330)").assertIsDisplayed()
        compose.onNodeWithTag("member_item_2330").performClick()
        assertEquals("sec:TWSE:2330", navSelection)

        // 3. Theme Detail Screen: Verify Member
        compose.setContent {
            ThemeDetailScreen(
                uiState = ThemeDetailUiState.Success(
                    detail = TaxonomyDetail(
                        taxonomy = aiTheme,
                        members = listOf(quantaMember),
                        asOf = "2026-08-11T00:00:00Z",
                        dataStatus = DataStatus.FINAL,
                    )
                ),
                onSecurityClick = { market, code -> navSelection = "sec:$market:$code" },
                onRetry = {},
            )
        }

        compose.onNodeWithText("廣達 (2382)").assertIsDisplayed()

        // 4. Security Detail Screen: Verify Official Industry & Attached Themes
        val fullSecurity = Security(
            id = "sec_2330",
            code = "2330",
            name = "台積電",
            market = MarketCode.TWSE,
            securityType = SecurityType.COMMON_STOCK,
            status = SecurityStatus.ACTIVE,
            primaryIndustry = "半導體",
            listingDate = "1994-09-05",
            isActive = true,
            asOf = "2026-08-11T00:00:00Z",
            receivedAt = "2026-08-11T00:00:00Z",
            dataStatus = DataStatus.FINAL,
            themes = listOf(
                ThemeRef("t_ai", "AI_SERVER", "AI 伺服器"),
                ThemeRef("t_cpo", "CPO", "CPO 矽光子"),
            ),
        )

        compose.setContent {
            SecurityDetailScreen(state = SecurityDetailUiState.Success(fullSecurity))
        }

        compose.onNodeWithTag("security-detail-title").assertIsDisplayed()
        compose.onNodeWithText("主要產業：半導體").assertIsDisplayed()
        compose.onNodeWithText("所屬題材：AI 伺服器, CPO 矽光子").assertIsDisplayed()
    }
}
