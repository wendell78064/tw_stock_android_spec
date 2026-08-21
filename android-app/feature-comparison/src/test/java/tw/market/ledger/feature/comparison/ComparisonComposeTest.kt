package tw.market.ledger.feature.comparison

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.model.MarketCode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ComparisonComposeTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun testComparisonScreenDisplaysAiButtonAndCopiesPrompt() {
        val fakeApi = FakeComparisonApi()
        val vm = ComparisonViewModel(fakeApi)
        val t1 = SecurityTarget("2330", MarketCode.TWSE)
        val t2 = SecurityTarget("2317", MarketCode.TWSE)
        vm.setTargets(listOf(t1, t2))

        composeRule.setContent {
            ComparisonScreen(viewModel = vm, onNavigateBack = {})
        }

        composeRule.onNodeWithTag("btn_ai_comparison").assertIsDisplayed()

        // Trigger AI Comparison
        composeRule.onNodeWithTag("btn_ai_comparison").performClick()

        // Verify Prompt Card and Copy Button
        composeRule.onNodeWithTag("comparison_ai_prompt_card").assertIsDisplayed()
        composeRule.onNodeWithTag("btn_copy_comparison_prompt").assertIsDisplayed()

        // Click Copy
        composeRule.onNodeWithTag("btn_copy_comparison_prompt").performClick()
        composeRule.onNodeWithTag("comparison_ai_prompt_copied_banner").assertIsDisplayed()
        composeRule.onNodeWithText("已複製！").assertIsDisplayed()
    }
}
