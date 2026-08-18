package tw.market.ledger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.market.ledger.network.RealtimeQuoteClient
import okhttp3.OkHttpClient

class EndpointConfigurationTest {

    @Test
    fun testBuildConfigEndpointsAreNotEmptyAndFormatted() {
        assertNotNull(BuildConfig.API_BASE_URL)
        assertNotNull(BuildConfig.WS_BASE_URL)

        assertTrue("API_BASE_URL should start with http:// or https://",
            BuildConfig.API_BASE_URL.startsWith("http://") || BuildConfig.API_BASE_URL.startsWith("https://"))
        assertTrue("API_BASE_URL should end with trailing slash",
            BuildConfig.API_BASE_URL.endsWith("/"))

        assertTrue("WS_BASE_URL should start with ws:// or wss://",
            BuildConfig.WS_BASE_URL.startsWith("ws://") || BuildConfig.WS_BASE_URL.startsWith("wss://"))
        assertTrue("WS_BASE_URL should end with /v1/ws/quotes",
            BuildConfig.WS_BASE_URL.endsWith("/v1/ws/quotes"))
    }

    @Test
    fun testRealtimeQuoteClientRequiresExplicitServerUrl() {
        val testUrl = "wss://stock-api.orca-wave.com/v1/ws/quotes"
        val client = RealtimeQuoteClient(OkHttpClient(), testUrl)
        assertEquals(testUrl, client.serverUrl)
    }
}
