package tw.market.ledger.model

import org.junit.Assert.*
import org.junit.Test

class TechnicalIndicatorPreferencesTest {
    @Test fun defaultsAndCustomQueryAreStable() {
        val defaults = TechnicalIndicatorPreferences.Default
        assertEquals(14, defaults.rsi.period)
        assertNull(defaults.validationError())
        assertTrue(defaults.queryParameters().isEmpty())
        val custom = defaults.copy(rsi = RsiSettings(12), bollinger = BollingerSettings(15, "2.5"))
        assertEquals("12", custom.queryParameters()["rsi_period"])
        assertEquals("2.5", custom.queryParameters()["bollinger_stddev"])
    }

    @Test fun invalidPeriodsMacdBollingerAndDuplicatesAreRejected() {
        assertNotNull(TechnicalIndicatorPreferences.Default.copy(rsi = RsiSettings(0)).validationError())
        assertNotNull(TechnicalIndicatorPreferences.Default.copy(macd = MacdSettings(26, 12, 9)).validationError())
        assertNotNull(TechnicalIndicatorPreferences.Default.copy(bollinger = BollingerSettings(20, "0")).validationError())
        assertNotNull(TechnicalIndicatorPreferences.Default.copy(ma = MaSettings(listOf(5, 5))).validationError())
    }
}
