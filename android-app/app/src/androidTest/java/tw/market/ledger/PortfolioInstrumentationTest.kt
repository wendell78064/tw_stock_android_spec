package tw.market.ledger

import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.portfolio.domain.PortfolioDashboard
import tw.market.ledger.feature.portfolio.presentation.*
import tw.market.ledger.model.*

class PortfolioInstrumentationTest {
    @get:Rule val compose = createComposeRule()

    @Test fun deterministicBuyBuyPartialSellAndOversellScenario() {
        compose.setContent { DeterministicScenario() }
        compose.onNodeWithTag("portfolio-empty").assertIsDisplayed()
        compose.onNodeWithText("新增第一筆交易").performClick()
        compose.onNodeWithText("1000 股 · 均價 10").assertExists()
        compose.onNodeWithTag("add-transaction").performClick()
        compose.onNodeWithText("1500 股 · 均價 12").assertExists()
        compose.onNodeWithTag("add-transaction").performClick()
        compose.onNodeWithText("900 股 · 均價 12").assertExists()
        compose.onNodeWithTag("add-transaction").performClick()
        compose.onNodeWithText("賣出股數超過目前可用持股").assertExists()
        compose.onNodeWithText("900 股 · 均價 12").assertExists()
    }
}

@Composable
private fun DeterministicScenario() {
    var stage by remember { mutableIntStateOf(0) }
    if (stage == 0) {
        PortfolioDashboardScreen(PortfolioUiState.Empty, onAdd={stage=1})
        return
    }
    val quantity = when (stage) { 1 -> 1000L; 2 -> 1500L; else -> 900L }
    val average = if (stage == 1) "10" else "12"
    val cost = if (stage == 1) "10000" else if (stage == 2) "18000" else "10800"
    val holding = PortfolioHolding("2330", "台積電", MarketCode.TWSE, quantity, average, cost,
        if (stage >= 3) "1800" else "0", "15", "2026-08-10", DataStatus.FINAL,
        (quantity * 15).toString(), ((quantity * 15) - cost.toLong()).toString(), "25", "100")
    val summary = PortfolioSummary(holding.marketValue, cost, holding.unrealizedPnl,
        holding.realizedPnl, "25", 1, "2026-08-10", DataStatus.FINAL)
    PortfolioDashboardScreen(PortfolioUiState.Success(PortfolioDashboard(
        Portfolio("fixture", "Fixture", "TWD", true), summary, listOf(holding), emptyList())),
        onAdd={ if (stage < 3) stage++ else stage=4 })
    if (stage == 4) Text("賣出股數超過目前可用持股")
}
