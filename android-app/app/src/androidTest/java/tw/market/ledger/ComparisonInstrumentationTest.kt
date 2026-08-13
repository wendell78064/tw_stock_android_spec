package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.comparison.ComparisonScreen
import tw.market.ledger.feature.comparison.ComparisonViewModel
import tw.market.ledger.feature.comparison.FakeComparisonApi
import tw.market.ledger.feature.comparison.SecurityTarget
import tw.market.ledger.model.MarketCode

class ComparisonInstrumentationTest {
    @get:Rule val composeTestRule = createComposeRule()

    @Test
    fun testComparisonFullUiFlow() {
        val fakeApi = FakeComparisonApi()
        val vm = ComparisonViewModel(fakeApi)
        val t1 = SecurityTarget("2330", MarketCode.TWSE)
        val t2 = SecurityTarget("2317", MarketCode.TWSE)
        vm.setTargets(listOf(t1, t2))

        composeTestRule.setContent {
            ComparisonScreen(viewModel = vm, onNavigateBack = {})
        }
        composeTestRule.onNodeWithTag("comparison_screen").assertIsDisplayed()
        composeTestRule.onNodeWithTag("normalized_canvas_chart").assertIsDisplayed()
        composeTestRule.onNodeWithTag("sec_summary_2330").assertIsDisplayed()
    }
}
