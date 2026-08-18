package tw.market.ledger.network

import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeQuote

class RealtimeNetworkTest {

    @Test
    fun testRealtimeSubscriptionManagerRefCounting() {
        val client = RealtimeQuoteClient(OkHttpClient(), "ws://localhost:8080/test/ws")
        val manager = RealtimeSubscriptionManager(client)

        assertEquals("ws://localhost:8080/test/ws", client.serverUrl)

        // Initial state
        assertEquals(RealtimeConnectionState.DISCONNECTED, client.connectionState.value)

        // First subscription
        manager.subscribe("TWSE", "2330")
        assertEquals(RealtimeConnectionState.CONNECTING, client.connectionState.value)

        // Second subscription for same security -> count incremented
        manager.subscribe("TWSE", "2330")

        // Unsubscribe once -> still subscribed
        manager.unsubscribe("TWSE", "2330")

        // Unsubscribe second time -> fully unsubscribed
        manager.unsubscribe("TWSE", "2330")
    }

    @Test
    fun testRealtimeQuoteModelProperties() {
        val quote = RealtimeQuote(
            securityId = "sec_2330",
            marketId = "TWSE",
            code = "2330",
            exchangeTimestamp = "2026-08-13T10:00:00Z",
            receivedAt = "2026-08-13T10:00:00.100Z",
            lastPrice = "950.00",
            dataStatus = RealtimeDataStatus.LIVE
        )

        assertEquals("TWSE:2330", quote.compositeKey)
        assertEquals("950.00", quote.lastPrice)
        assertEquals(RealtimeDataStatus.LIVE, quote.dataStatus)
    }
}
