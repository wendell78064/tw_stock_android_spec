package tw.market.ledger

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextReplacement
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import tw.market.ledger.feature.security.presentation.IndicatorSettingsDialog
import tw.market.ledger.feature.security.presentation.IndicatorSettingsUiState
import tw.market.ledger.model.MacdSettings
import tw.market.ledger.model.RsiSettings
import tw.market.ledger.model.TechnicalIndicatorPreferences

class IndicatorSettingsInstrumentationTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun rsiEditPersistsThroughSaveCallbackAndResetRestoresDefault() {
        var saved: TechnicalIndicatorPreferences? = null
        composeRule.setContent {
            IndicatorSettingsDialog(TechnicalIndicatorPreferences.Default,
                IndicatorSettingsUiState.Loaded(TechnicalIndicatorPreferences.Default), {}, { saved = it }, {})
        }
        composeRule.onNodeWithTag("setting-RSI").performClick()
        composeRule.onNodeWithTag("parameter-RSI period").performTextReplacement("12")
        composeRule.onNodeWithText("完成").performClick()
        composeRule.onNodeWithText("儲存").performClick()
        assertEquals(12, saved?.rsi?.period)
    }

    @Test fun invalidMacdShowsExplicitValidationError() {
        val invalid = TechnicalIndicatorPreferences.Default.copy(macd = MacdSettings(26, 12, 9))
        composeRule.setContent {
            IndicatorSettingsDialog(invalid,
                IndicatorSettingsUiState.ValidationError(invalid, invalid.validationError()!!), {}, {}, {})
        }
        composeRule.onNodeWithTag("settings-validation-error").assertIsDisplayed()
        composeRule.onNodeWithText("MACD slow 必須大於 fast").assertIsDisplayed()
    }
}
