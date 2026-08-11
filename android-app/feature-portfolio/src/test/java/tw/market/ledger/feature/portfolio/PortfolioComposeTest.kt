package tw.market.ledger.feature.portfolio

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.portfolio.presentation.*
import tw.market.ledger.model.*

@RunWith(RobolectricTestRunner::class) @Config(sdk=[35])
class PortfolioComposeTest {
    @get:Rule val compose = createComposeRule()

    @Test fun dashboardSummaryHoldingAndSortAreVisible() {
        compose.setContent { PortfolioDashboardScreen(PortfolioUiState.Success(dashboard)) }
        compose.onNodeWithTag("portfolio-dashboard").assertIsDisplayed()
        compose.onNodeWithTag("holding-2330").assertExists()
        compose.onNodeWithText("總市值 15000").assertIsDisplayed()
        compose.onNodeWithText("CODE").performClick()
    }

    @Test fun emptyStateOffersFirstTransaction() {
        compose.setContent { PortfolioDashboardScreen(PortfolioUiState.Empty) }
        compose.onNodeWithTag("portfolio-empty").assertIsDisplayed()
        compose.onNodeWithText("新增第一筆交易").assertIsDisplayed()
    }

    @Test fun addTransactionSwitchAndValidationAreExplicit() {
        compose.setContent { AddTransactionScreen({ if (it == "2330") 100L else null }, {}, {}) }
        compose.onNodeWithTag("add-transaction-screen").assertIsDisplayed()
        compose.onAllNodesWithText("SELL").onFirst().performClick()
        compose.onNodeWithText("請選擇股票").assertExists()
    }

    @Test fun holdingDetailShowsTransactionsAndDeleteConfirmation() {
        compose.setContent { HoldingDetailScreen(holding, listOf(transaction), {}, {}) }
        compose.onNodeWithTag("holding-detail").assertIsDisplayed()
        compose.onNodeWithText("BUY 1000 股 @ 10").assertExists()
        compose.onNodeWithText("Delete").performClick()
        compose.onNodeWithText("刪除交易？").assertIsDisplayed()
    }
}

class TransactionValidationTest {
    @Test fun buySellDecimalAndAvailableSharesValidation() {
        val base = TransactionFormState("2330", TransactionSide.SELL,
            "2026-08-11T09:00:00+08:00", "101", "10", "0", LotType.ODD_LOT)
        org.junit.Assert.assertEquals("賣出股數超過目前可用持股", base.error(100))
        org.junit.Assert.assertNull(base.copy(quantity="100").error(100))
        org.junit.Assert.assertEquals("成交價格必須大於 0", base.copy(price="0").error(1000))
    }
}
