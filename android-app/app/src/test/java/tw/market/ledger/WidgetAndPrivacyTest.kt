package tw.market.ledger

import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.market.ledger.ui.TaiwanMarketFormatter

class WidgetAndPrivacyTest {

    @Test
    fun testFinancialFormattingStandard() {
        val price = BigDecimal("950.50")
        val shares = 2000L
        val amount = BigDecimal("1901000.00")
        val pnl = BigDecimal("15000.00")
        val pct = BigDecimal("3.45")

        assertEquals("950.50", TaiwanMarketFormatter.formatPrice(price, privacy = false))
        assertEquals("2,000", TaiwanMarketFormatter.formatShares(shares, privacy = false))
        assertEquals("NT$ 1,901,000.00", TaiwanMarketFormatter.formatAmount(amount, privacy = false))
        assertEquals("+15,000.00", TaiwanMarketFormatter.formatPnl(pnl, privacy = false))
        assertEquals("+3.45%", TaiwanMarketFormatter.formatPercent(pct, privacy = false))
    }

    @Test
    fun testPrivacyModeMasksValues() {
        val price = BigDecimal("950.50")
        val shares = 2000L
        val amount = BigDecimal("1901000.00")
        val pnl = BigDecimal("15000.00")
        val pct = BigDecimal("3.45")

        assertEquals("••••••", TaiwanMarketFormatter.formatPrice(price, privacy = true))
        assertEquals("••••••", TaiwanMarketFormatter.formatShares(shares, privacy = true))
        assertEquals("••••••", TaiwanMarketFormatter.formatAmount(amount, privacy = true))
        assertEquals("••••••", TaiwanMarketFormatter.formatPnl(pnl, privacy = true))
        assertEquals("••••••", TaiwanMarketFormatter.formatPercent(pct, privacy = true))
    }

    @Test
    fun testTaipeiDateTimeFormatting() {
        val iso = "2026-08-14T01:30:00Z"
        val formatted = TaiwanMarketFormatter.formatTaipeiDateTime(iso)
        assertTrue(formatted.contains("2026/08/14"))
        assertTrue(formatted.contains("09:30"))

        val timeOnly = TaiwanMarketFormatter.formatTaipeiTime(iso)
        assertEquals("09:30", timeOnly)
    }
}
