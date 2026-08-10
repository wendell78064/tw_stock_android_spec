package tw.market.ledger.feature.security

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import tw.market.ledger.feature.security.data.IndicatorSettings
import tw.market.ledger.model.RsiSettings
import tw.market.ledger.model.TechnicalIndicatorPreferences

@RunWith(RobolectricTestRunner::class)
class IndicatorSettingsTest {
    @Test fun customSettingsSerializeAndReset() = runTest {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val store = IndicatorSettings(context)
        store.save(TechnicalIndicatorPreferences.Default.copy(rsi = RsiSettings(12)))
        assertEquals(12, store.preferences.first().rsi.period)
        store.resetAll()
        assertEquals(14, store.preferences.first().rsi.period)
    }
}
