package tw.market.ledger.network

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeQuote

class RealtimeNetworkTest {

    private class FakeSubscriptionClient : RealtimeSubscriptionClient {
        data class Call(
            val action: String,
            val market: String,
            val code: String,
            val quoteTypes: Set<RealtimeQuoteType>,
        )

        private val mutableQuotes = MutableSharedFlow<RealtimeQuote>(extraBufferCapacity = 4)
        override val quotesFlow: SharedFlow<RealtimeQuote> = mutableQuotes
        val calls = mutableListOf<Call>()
        val activeTargets = mutableSetOf<RealtimeSubscriptionTarget>()
        var connectCount = 0

        override fun connect() {
            connectCount++
        }

        override fun subscribe(
            market: String,
            code: String,
            quoteTypes: Set<RealtimeQuoteType>,
        ) {
            calls += Call("subscribe", market, code, quoteTypes)
            quoteTypes.forEach { activeTargets += RealtimeSubscriptionTarget(market, code, it) }
        }

        override fun unsubscribe(
            market: String,
            code: String,
            quoteTypes: Set<RealtimeQuoteType>,
        ) {
            calls += Call("unsubscribe", market, code, quoteTypes)
            quoteTypes.forEach { activeTargets -= RealtimeSubscriptionTarget(market, code, it) }
        }
    }

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
    fun currentViewOwnsTickAndBidAskWithoutDuplicateBrokerSubscriptions() {
        val client = FakeSubscriptionClient()
        val manager = RealtimeSubscriptionManager(client)
        val both = setOf(RealtimeQuoteType.TICK, RealtimeQuoteType.BID_ASK)

        manager.acquireCurrentView("detail-1", "TWSE", "2330")
        manager.acquireCurrentView("detail-1", "TWSE", "2330")
        manager.acquireCurrentView("detail-2", "TWSE", "2330")

        assertEquals(1, client.connectCount)
        assertEquals(
            listOf(FakeSubscriptionClient.Call("subscribe", "TWSE", "2330", both)),
            client.calls,
        )

        manager.releaseCurrentView("detail-1", "TWSE", "2330")
        assertEquals(1, client.calls.size)
        manager.releaseCurrentView("detail-2", "TWSE", "2330")
        assertEquals(
            FakeSubscriptionClient.Call("unsubscribe", "TWSE", "2330", both),
            client.calls.last(),
        )
    }

    @Test
    fun tickAndBidAskOwnershipRemainIndependentAcrossConsumers() {
        val client = FakeSubscriptionClient()
        val manager = RealtimeSubscriptionManager(client)

        manager.acquireCurrentView("detail", "TWSE", "2330")
        manager.subscribe("TWSE", "2330")
        manager.releaseCurrentView("detail", "TWSE", "2330")

        assertEquals(
            setOf(RealtimeQuoteType.BID_ASK),
            client.calls.last().quoteTypes,
        )
        manager.unsubscribe("TWSE", "2330")
        assertEquals(setOf(RealtimeQuoteType.TICK), client.calls.last().quoteTypes)
    }

    @Test
    fun reconnectDesiredSetContainsOnlyCurrentSecurity() {
        val client = RealtimeQuoteClient(OkHttpClient(), "ws://localhost:8080/test/ws")
        val both = setOf(RealtimeQuoteType.TICK, RealtimeQuoteType.BID_ASK)

        client.subscribe("TWSE", "2330", both)
        client.unsubscribe("TWSE", "2330", both)
        client.subscribe("TWSE", "2454", both)

        val targets = client.activeSubscriptionTargets()
        assertEquals(1, targets.size)
        assertEquals("TWSE", targets.single()["market"])
        assertEquals("2454", targets.single()["code"])
        assertEquals(listOf("bid_ask", "tick"), targets.single()["quote_types"])
    }

    @Test
    fun portfolioMembershipIsTickOnlyDeduplicatedAndSetDiffed() {
        val client = FakeSubscriptionClient()
        val manager = RealtimeSubscriptionManager(
            client,
            portfolioRealtimeEnabled = true,
        )

        val first = manager.updatePortfolioMembership(
            setOf(
                RealtimeSecurityTarget("twse", "2330"),
                RealtimeSecurityTarget("TWSE", "2330"),
                RealtimeSecurityTarget("TPEX", "6488"),
            )
        )
        assertTrue(first.enabled)
        assertEquals(2, first.added.size)
        assertTrue(client.calls.all { it.quoteTypes == setOf(RealtimeQuoteType.TICK) })

        val unchanged = manager.updatePortfolioMembership(
            setOf(
                RealtimeSecurityTarget("TWSE", "2330"),
                RealtimeSecurityTarget("TPEX", "6488"),
            )
        )
        assertTrue(unchanged.added.isEmpty())
        assertTrue(unchanged.removed.isEmpty())
        assertEquals(2, client.calls.size)

        val changed = manager.updatePortfolioMembership(
            setOf(
                RealtimeSecurityTarget("TPEX", "6488"),
                RealtimeSecurityTarget("TWSE", "2308"),
            )
        )
        assertEquals(setOf(RealtimeSecurityTarget("TWSE", "2308")), changed.added)
        assertEquals(setOf(RealtimeSecurityTarget("TWSE", "2330")), changed.removed)
        assertEquals(
            setOf(
                RealtimeSubscriptionTarget("TPEX", "6488", RealtimeQuoteType.TICK),
                RealtimeSubscriptionTarget("TWSE", "2308", RealtimeQuoteType.TICK),
            ),
            client.activeTargets,
        )
    }

    @Test
    fun portfolioAndCurrentViewShareTickButKeepBidAskIndependent() {
        val client = FakeSubscriptionClient()
        val manager = RealtimeSubscriptionManager(
            client,
            portfolioRealtimeEnabled = true,
        )

        manager.updatePortfolioMembership(setOf(RealtimeSecurityTarget("TWSE", "2330")))
        manager.acquireCurrentView("P2_DETAIL", "TWSE", "2330")
        assertEquals(
            listOf(
                FakeSubscriptionClient.Call(
                    "subscribe",
                    "TWSE",
                    "2330",
                    setOf(RealtimeQuoteType.TICK),
                ),
                FakeSubscriptionClient.Call(
                    "subscribe",
                    "TWSE",
                    "2330",
                    setOf(RealtimeQuoteType.BID_ASK),
                ),
            ),
            client.calls,
        )

        manager.releaseCurrentView("P2_DETAIL", "TWSE", "2330")
        assertEquals(setOf(RealtimeQuoteType.BID_ASK), client.calls.last().quoteTypes)
        assertTrue(
            RealtimeSubscriptionTarget("TWSE", "2330", RealtimeQuoteType.TICK) in
                client.activeTargets
        )
        manager.releasePortfolioMembership()
        assertEquals(setOf(RealtimeQuoteType.TICK), client.calls.last().quoteTypes)
        assertTrue(client.activeTargets.isEmpty())
    }

    @Test
    fun portfolioGateDefaultsDisabledAndInvalidTargetsAreReported() {
        val disabledClient = FakeSubscriptionClient()
        val disabled = RealtimeSubscriptionManager(disabledClient)
            .updatePortfolioMembership(setOf(RealtimeSecurityTarget("TWSE", "2330")))
        assertFalse(disabled.enabled)
        assertTrue(disabledClient.calls.isEmpty())

        val enabledClient = FakeSubscriptionClient()
        val enabled = RealtimeSubscriptionManager(
            enabledClient,
            portfolioRealtimeEnabled = true,
        ).updatePortfolioMembership(
            setOf(
                RealtimeSecurityTarget("UNKNOWN", "2330"),
                RealtimeSecurityTarget("TWSE", "23X0"),
            )
        )
        assertEquals(2, enabled.rejected.size)
        assertTrue(enabledClient.calls.isEmpty())
    }

    @Test
    fun watchlistMembershipIsTickOnlyDeduplicatedSetDiffedAndSafelyGated() {
        val disabledClient = FakeSubscriptionClient()
        val disabled = RealtimeSubscriptionManager(disabledClient)
            .updateWatchlistMembership(setOf(RealtimeSecurityTarget("TWSE", "2330")))
        assertFalse(disabled.enabled)
        assertTrue(disabledClient.calls.isEmpty())

        val client = FakeSubscriptionClient()
        val manager = RealtimeSubscriptionManager(client, watchlistRealtimeEnabled = true)
        val first = manager.updateWatchlistMembership(
            setOf(
                RealtimeSecurityTarget("twse", "2330"),
                RealtimeSecurityTarget("TWSE", "2330"),
                RealtimeSecurityTarget("TPEX", "6488"),
                RealtimeSecurityTarget("UNKNOWN", "9999"),
            )
        )
        assertEquals(2, first.added.size)
        assertEquals(1, first.rejected.size)
        assertTrue(client.calls.all { it.quoteTypes == setOf(RealtimeQuoteType.TICK) })

        val unchanged = manager.updateWatchlistMembership(
            setOf(
                RealtimeSecurityTarget("TWSE", "2330"),
                RealtimeSecurityTarget("TPEX", "6488"),
            )
        )
        assertTrue(unchanged.added.isEmpty())
        assertTrue(unchanged.removed.isEmpty())

        val changed = manager.updateWatchlistMembership(
            setOf(
                RealtimeSecurityTarget("TPEX", "6488"),
                RealtimeSecurityTarget("TWSE", "2454"),
            )
        )
        assertEquals(setOf(RealtimeSecurityTarget("TWSE", "2454")), changed.added)
        assertEquals(setOf(RealtimeSecurityTarget("TWSE", "2330")), changed.removed)
        manager.releaseWatchlistMembership()
        assertTrue(client.activeTargets.isEmpty())
    }

    @Test
    fun p0P2AndP4ShareTickWhileBidAskAndOwnerReleasesRemainIndependent() {
        val client = FakeSubscriptionClient()
        val manager = RealtimeSubscriptionManager(
            client,
            portfolioRealtimeEnabled = true,
            watchlistRealtimeEnabled = true,
        )

        manager.updatePortfolioMembership(setOf(RealtimeSecurityTarget("TWSE", "2330")))
        manager.updateWatchlistMembership(setOf(RealtimeSecurityTarget("TWSE", "2330")))
        manager.acquireCurrentView("P2_DETAIL", "TWSE", "2330")

        assertEquals(1, client.calls.count { it.action == "subscribe" && it.quoteTypes == setOf(RealtimeQuoteType.TICK) })
        assertEquals(1, client.calls.count { it.action == "subscribe" && it.quoteTypes == setOf(RealtimeQuoteType.BID_ASK) })

        manager.releaseCurrentView("P2_DETAIL", "TWSE", "2330")
        manager.releaseWatchlistMembership()
        assertTrue(RealtimeSubscriptionTarget("TWSE", "2330", RealtimeQuoteType.TICK) in client.activeTargets)
        manager.releasePortfolioMembership()
        assertTrue(client.activeTargets.isEmpty())
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
