package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import java.util.UUID
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.screener.PresetItemCard
import tw.market.ledger.feature.screener.PresetScreener
import tw.market.ledger.feature.screener.SavedScreenerCard
import tw.market.ledger.feature.screener.ScreenerResultItemCard
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.SavedScreener
import tw.market.ledger.model.ScreenerExpression
import tw.market.ledger.model.ScreenerResultSecurity

class ScreenerInstrumentationTest {
    @get:Rule val composeTestRule = createComposeRule()

    @Test
    fun testPresetCardRenderAndClick() {
        var clicked = false
        val preset = PresetScreener(
            id = "preset_test",
            name = "強勢選股",
            description = "測試說明",
            expression = ScreenerExpression("AND")
        )
        composeTestRule.setContent {
            PresetItemCard(preset = preset, onRun = { clicked = true })
        }
        composeTestRule.onNodeWithTag("preset_item_preset_test").assertIsDisplayed()
        composeTestRule.onNodeWithTag("preset_item_preset_test").performClick()
        assert(clicked)
    }

    @Test
    fun testSavedScreenerCardRender() {
        val saved = SavedScreener(
            id = UUID.randomUUID(),
            name = "自訂策略1",
            description = "高籌碼動能",
            expression = ScreenerExpression("AND"),
            createdAt = "2026-08-11T00:00:00Z",
            updatedAt = "2026-08-11T00:00:00Z"
        )
        composeTestRule.setContent {
            SavedScreenerCard(saved = saved, onRun = {}, onDelete = {})
        }
        composeTestRule.onNodeWithTag("saved_screener_item_${saved.id}").assertIsDisplayed()
    }

    @Test
    fun testScreenerResultCardRender() {
        val security = ScreenerResultSecurity(
            securityId = UUID.randomUUID(),
            code = "2330",
            name = "台積電",
            market = "TWSE",
            industryName = "半導體",
            close = "950.00",
            returnPct = "2.50",
            matchedConditions = listOf("PASS RSI14 LT 30"),
            dataStatus = DataStatus.FINAL
        )
        composeTestRule.setContent {
            ScreenerResultItemCard(security = security, onClick = {})
        }
        composeTestRule.onNodeWithTag("result_item_2330", useUnmergedTree = true)
            .assertIsDisplayed()
    }
}
