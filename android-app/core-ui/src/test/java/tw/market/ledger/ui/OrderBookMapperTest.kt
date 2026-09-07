package tw.market.ledger.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.market.ledger.model.RealtimeDataStatus
import java.math.BigDecimal

class OrderBookMapperTest {

    @Test
    fun `maps five bid levels and five ask levels accurately`() {
        val bids = listOf("100.0", "99.5", "99.0", "98.5", "98.0")
        val bidVols = listOf(10, 20, 30, 40, 50)
        val asks = listOf("100.5", "101.0", "101.5", "102.0", "102.5")
        val askVols = listOf(15, 25, 35, 45, 55)

        val model = OrderBookMapper.map(
            bidPrices = bids,
            bidVolumes = bidVols,
            askPrices = asks,
            askVolumes = askVols,
            status = RealtimeDataStatus.LIVE,
            referencePrice = BigDecimal("100.0"),
        )

        assertEquals(5, model.bids.size)
        assertEquals(5, model.asks.size)
        assertEquals(RealtimeDataStatus.LIVE, model.status)

        // Asks top-to-bottom: 賣五 down to 賣一
        assertEquals("賣五", model.asks[0].levelName)
        assertEquals("102.5", model.asks[0].price)
        assertEquals(55, model.asks[0].volume)
        assertTrue(model.asks[0].isAsk)

        assertEquals("賣一", model.asks[4].levelName)
        assertEquals("100.5", model.asks[4].price)
        assertEquals(15, model.asks[4].volume)

        // Bids top-to-bottom: 買一 down to 買五
        assertEquals("買一", model.bids[0].levelName)
        assertEquals("100.0", model.bids[0].price)
        assertEquals(10, model.bids[0].volume)
        assertFalse(model.bids[0].isAsk)

        assertEquals("買五", model.bids[4].levelName)
        assertEquals("98.0", model.bids[4].price)
        assertEquals(50, model.bids[4].volume)
    }

    @Test
    fun `fewer than five levels does not fabricate missing levels or convert to zero`() {
        // Only 2 levels provided by exchange
        val bids = listOf("500.0", "499.0")
        val bidVols = listOf(5, 8)
        val asks = listOf("501.0", "502.0")
        val askVols = listOf(3, 7)

        val model = OrderBookMapper.map(
            bidPrices = bids,
            bidVolumes = bidVols,
            askPrices = asks,
            askVolumes = askVols,
            status = RealtimeDataStatus.LIVE,
        )

        // Count coerced to max(2, 2) = 2, so only 2 levels rendered
        assertEquals(2, model.bids.size)
        assertEquals(2, model.asks.size)

        assertEquals("賣二", model.asks[0].levelName)
        assertEquals("502.0", model.asks[0].price)
        assertEquals(7, model.asks[0].volume)

        assertEquals("賣一", model.asks[1].levelName)
        assertEquals("501.0", model.asks[1].price)
        assertEquals(3, model.asks[1].volume)

        assertEquals("買一", model.bids[0].levelName)
        assertEquals("500.0", model.bids[0].price)
        assertEquals(5, model.bids[0].volume)

        assertEquals("買二", model.bids[1].levelName)
        assertEquals("499.0", model.bids[1].price)
        assertEquals(8, model.bids[1].volume)
    }

    @Test
    fun `missing prices and volumes remain null and are not fabricated as zero`() {
        val bids = listOf("100.0")
        val bidVols = emptyList<Int>() // No volume
        val asks = emptyList<String>() // No ask price
        val askVols = listOf(12)

        val model = OrderBookMapper.map(
            bidPrices = bids,
            bidVolumes = bidVols,
            askPrices = asks,
            askVolumes = askVols,
            status = RealtimeDataStatus.STALE,
        )

        assertEquals(1, model.bids.size)
        assertEquals("100.0", model.bids[0].price)
        assertNull(model.bids[0].volume)

        assertEquals(1, model.asks.size)
        assertNull(model.asks[0].price)
        assertEquals(12, model.asks[0].volume)
        assertEquals(RealtimeDataStatus.STALE, model.status)
    }
}
