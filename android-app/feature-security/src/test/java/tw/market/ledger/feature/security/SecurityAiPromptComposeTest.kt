package tw.market.ledger.feature.security

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
import tw.market.ledger.feature.security.presentation.SecurityAiPromptScreen
import tw.market.ledger.feature.security.presentation.SecurityAiPromptUiState
import tw.market.ledger.model.AnalysisPrompt
import tw.market.ledger.model.DataStatus

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class SecurityAiPromptComposeTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun loadingStateDisplaysSpinner() {
        composeRule.setContent {
            SecurityAiPromptScreen(state = SecurityAiPromptUiState.Loading)
        }
        composeRule.onNodeWithTag("ai-prompt-loading").assertIsDisplayed()
    }

    @Test
    fun successStateDisplaysPromptAndAllowsCopy() {
        val dummyPrompt = AnalysisPrompt(
            security = security("2330"),
            asOf = "2026-08-20T15:30:00Z",
            generatedAt = "2026-08-20T15:30:05Z",
            prompt = "【TW Market Ledger 智慧台股量化分析 Prompt】\n• 股票名稱與代號：測試科技 (2330)",
            characterCount = 85,
            dataStatus = DataStatus.FINAL,
            portfolioIncluded = false,
        )

        composeRule.setContent {
            SecurityAiPromptScreen(state = SecurityAiPromptUiState.Success(dummyPrompt))
        }

        composeRule.onNodeWithTag("security-ai-prompt-title").assertIsDisplayed()
        composeRule.onNodeWithText("2330 測試科技 AI 分析 Prompt").assertIsDisplayed()
        composeRule.onNodeWithText("【TW Market Ledger 智慧台股量化分析 Prompt】\n• 股票名稱與代號：測試科技 (2330)").assertIsDisplayed()
        composeRule.onNodeWithTag("security-ai-prompt-copy-btn").assertIsDisplayed()

        // Perform click to test copy button
        composeRule.onNodeWithTag("security-ai-prompt-copy-btn").performClick()
        composeRule.onNodeWithTag("security-ai-prompt-copied-banner").assertIsDisplayed()
        composeRule.onNodeWithText("已複製！").assertIsDisplayed()
    }

    @Test
    fun errorStateDisplaysMessageAndRetry() {
        var retried = false
        composeRule.setContent {
            SecurityAiPromptScreen(
                state = SecurityAiPromptUiState.Error("連線超時"),
                onRetry = { retried = true }
            )
        }

        composeRule.onNodeWithText("載入 AI Prompt 失敗：連線超時").assertIsDisplayed()
        composeRule.onNodeWithText("重試").assertIsDisplayed().performClick()
        assert(retried)
    }
}
