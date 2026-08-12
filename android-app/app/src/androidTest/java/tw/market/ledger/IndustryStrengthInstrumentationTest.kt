package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.industry.presentation.StrengthDetailScreen
import tw.market.ledger.feature.industry.presentation.StrengthDetailUiState
import tw.market.ledger.feature.industry.presentation.StrengthRankingScreen
import tw.market.ledger.feature.industry.presentation.StrengthRankingUiState
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.StrengthComponents
import tw.market.ledger.model.TaxonomyLeader
import tw.market.ledger.model.TaxonomyStrength
import tw.market.ledger.model.TaxonomyStrengthDetail

class IndustryStrengthInstrumentationTest {
    @get:Rule
    val compose = createComposeRule()

    private val semiStrength = TaxonomyStrength(
        id = "str_semi",
        taxonomyId = "ind_24",
        taxonomyCode = "24",
        taxonomyName = "半導體",
        taxonomyType = "OFFICIAL",
        tradeDate = "2026-08-11",
        window = 20,
        equalWeightReturn = "4.50",
        marketCapWeightedReturn = null,
        totalMembers = 10,
        validMembers = 10,
        coverageRatio = "1.0000",
        advancers = 7,
        decliners = 2,
        unchanged = 1,
        advanceRatio = "0.7000",
        aboveMa20Pct = "0.8000",
        aboveMa60Pct = "0.6000",
        foreignNetAmount = "5000000",
        investmentTrustNetAmount = "1000000",
        dealerNetAmount = "500000",
        marginBalanceChange = "200000",
        shortBalanceChange = "10000",
        lendingBalanceChange = null,
        turnoverAmount = "5000000000",
        turnoverShare = null,
        turnoverMomentum = "1.2000",
        components = StrengthComponents(
            momentumScore = "85.00",
            breadthScore = "75.00",
            technicalScore = "70.00",
            institutionalScore = "80.00",
            turnoverScore = "60.00",
        ),
        strengthScore = "78.50",
        componentCoverage = "1.0000",
        rank = 1,
        algorithmVersion = "twml-industry-strength-v1",
        dataStatus = DataStatus.FINAL,
        asOf = "2026-08-11T00:00:00Z",
    )

    private val aiThemeStrength = semiStrength.copy(
        id = "str_ai",
        taxonomyId = "t_ai",
        taxonomyCode = "AI_SERVER",
        taxonomyName = "AI 伺服器",
        taxonomyType = "CUSTOM",
        strengthScore = "82.10",
    )

    private val tsmcLeader = TaxonomyLeader(
        securityId = "sec_2330",
        code = "2330",
        name = "台積電",
        market = MarketCode.TWSE,
        returnPct = "5.25",
        latestClose = "1000.0",
        foreignNet = "5000000",
        dataStatus = DataStatus.FINAL,
    )

    private val umcLaggard = TaxonomyLeader(
        securityId = "sec_2303",
        code = "2303",
        name = "聯電",
        market = MarketCode.TWSE,
        returnPct = "-1.20",
        latestClose = "50.0",
        foreignNet = "-1000000",
        dataStatus = DataStatus.FINAL,
    )

    @Test
    fun strengthRankingScreenRendersAndSwitchesWindow() {
        var selectedWindow = 20
        compose.setContent {
            StrengthRankingScreen(
                uiState = StrengthRankingUiState.Success(
                    strengths = listOf(semiStrength),
                    window = selectedWindow,
                    sort = "strength",
                    isIndustry = true,
                ),
                onWindowSelect = { selectedWindow = it },
                onSortSelect = {},
                onTabSelect = {},
                onTaxonomyClick = { _, _ -> },
                onRetry = {},
            )
        }

        compose.onNodeWithText("半導體 (24)").assertIsDisplayed()
        compose.onNodeWithText("78.50").assertIsDisplayed()
        compose.onNodeWithTag("chip_window_5").performClick()
        assertEquals(5, selectedWindow)
    }

    @Test
    fun strengthDetailScreenRendersScoreBreakdownAndLeaders() {
        var clickedSec: String? = null
        compose.setContent {
            StrengthDetailScreen(
                uiState = StrengthDetailUiState.Success(
                    detail = TaxonomyStrengthDetail(
                        snapshot = semiStrength,
                        leaders = listOf(tsmcLeader),
                        laggards = listOf(umcLaggard),
                    ),
                    history = listOf(semiStrength),
                    window = 20,
                ),
                onWindowSelect = {},
                onSecurityClick = { market, code -> clickedSec = "$market:$code" },
                onRetry = {},
            )
        }

        compose.onNodeWithText("半導體 (24) - 強度明細").assertIsDisplayed()
        compose.onNodeWithText("5大成分分數拆解").assertIsDisplayed()
        compose.onNodeWithText("動能 (30%)").assertIsDisplayed()
        compose.onNodeWithText("85.00").assertIsDisplayed()
        compose.onNodeWithTag("leader_item_2330").performScrollTo().performClick()
        assertEquals("TWSE:2330", clickedSec)
    }

    @Test
    fun themeStrengthRankingRendersThemeItems() {
        compose.setContent {
            StrengthRankingScreen(
                uiState = StrengthRankingUiState.Success(
                    strengths = listOf(aiThemeStrength),
                    window = 20,
                    sort = "strength",
                    isIndustry = false,
                ),
                onWindowSelect = {},
                onSortSelect = {},
                onTabSelect = {},
                onTaxonomyClick = { _, _ -> },
                onRetry = {},
            )
        }

        compose.onNodeWithText("AI 伺服器 (AI_SERVER)").assertIsDisplayed()
        compose.onNodeWithText("82.10").assertIsDisplayed()
    }
}
