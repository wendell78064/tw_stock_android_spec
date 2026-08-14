package tw.market.ledger.ui

import java.math.BigDecimal
import java.math.RoundingMode
import java.text.DecimalFormat
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

object TaiwanMarketFormatter {
    val TAIPEI_ZONE: ZoneId = ZoneId.of("Asia/Taipei")

    private val priceFormat = DecimalFormat("#,##0.00")
    private val integerFormat = DecimalFormat("#,##0")
    private val percentFormat = DecimalFormat("+0.00%;-0.00%")

    fun formatPrice(value: BigDecimal?, privacy: Boolean = false): String {
        if (privacy) return "••••••"
        if (value == null) return "--"
        return priceFormat.format(value)
    }

    fun formatShares(shares: Long?, privacy: Boolean = false): String {
        if (privacy) return "••••••"
        if (shares == null) return "--"
        return integerFormat.format(shares)
    }

    fun formatAmount(amount: BigDecimal?, privacy: Boolean = false): String {
        if (privacy) return "••••••"
        if (amount == null) return "--"
        return "NT$ " + priceFormat.format(amount)
    }

    fun formatPnl(pnl: BigDecimal?, privacy: Boolean = false): String {
        if (privacy) return "••••••"
        if (pnl == null) return "--"
        if (pnl.compareTo(BigDecimal.ZERO) == 0) return "0.00"
        val prefix = if (pnl > BigDecimal.ZERO) "+" else ""
        return prefix + priceFormat.format(pnl)
    }

    fun formatPercent(pct: BigDecimal?, privacy: Boolean = false): String {
        if (privacy) return "••••••"
        if (pct == null) return "--"
        if (pct.compareTo(BigDecimal.ZERO) == 0) return "0.00%"
        val scaled = pct.divide(BigDecimal(100), 4, RoundingMode.HALF_UP)
        return percentFormat.format(scaled)
    }

    fun formatTaipeiDateTime(isoInstant: String?): String {
        if (isoInstant.isNullOrBlank()) return "--"
        return try {
            val instant = Instant.parse(isoInstant)
            DateTimeFormatter.ofPattern("yyyy/MM/dd HH:mm")
                .withZone(TAIPEI_ZONE)
                .format(instant)
        } catch (_: Exception) {
            isoInstant
        }
    }

    fun formatTaipeiTime(isoInstant: String?): String {
        if (isoInstant.isNullOrBlank()) return "--"
        return try {
            val instant = Instant.parse(isoInstant)
            DateTimeFormatter.ofPattern("HH:mm")
                .withZone(TAIPEI_ZONE)
                .format(instant)
        } catch (_: Exception) {
            isoInstant
        }
    }
}
