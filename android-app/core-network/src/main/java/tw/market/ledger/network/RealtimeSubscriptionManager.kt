package tw.market.ledger.network

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.model.RealtimeQuote

class RealtimeSubscriptionManager(
    private val client: RealtimeSubscriptionClient,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO + Job()),
) {
    private data class SubscriptionIdentity(
        val market: String,
        val code: String,
        val quoteType: RealtimeQuoteType,
    )

    private data class OwnerIdentity(
        val owner: String,
        val subscription: SubscriptionIdentity,
    )

    private val refCounts = mutableMapOf<SubscriptionIdentity, Int>()
    private val ownerSubscriptions = mutableSetOf<OwnerIdentity>()

    // Latest quote cache: "MARKET:CODE" -> RealtimeQuote
    private val _latestQuotes = MutableStateFlow<Map<String, RealtimeQuote>>(emptyMap())
    val latestQuotes: StateFlow<Map<String, RealtimeQuote>> = _latestQuotes.asStateFlow()

    init {
        scope.launch {
            client.quotesFlow.collect { quote ->
                val current: MutableMap<String, RealtimeQuote> = _latestQuotes.value.toMutableMap()
                current[quote.compositeKey] = quote
                _latestQuotes.value = current
            }
        }
    }

    @Synchronized
    fun subscribe(market: String, code: String) {
        val added = increment(market, code, setOf(RealtimeQuoteType.TICK))
        if (added.isNotEmpty()) {
            client.connect()
            client.subscribe(market, code, added)
        }
    }

    @Synchronized
    fun unsubscribe(market: String, code: String) {
        val removed = decrement(market, code, setOf(RealtimeQuoteType.TICK))
        if (removed.isNotEmpty()) {
            client.unsubscribe(market, code, removed)
        }
    }

    @Synchronized
    fun acquireCurrentView(owner: String, market: String, code: String) {
        val quoteTypes = RealtimeQuoteType.entries.toSet()
        val normalizedMarket = market.uppercase()
        val normalizedCode = code.uppercase()
        val newlyOwned = quoteTypes.filterTo(mutableSetOf()) { quoteType ->
            ownerSubscriptions.add(
                OwnerIdentity(
                    owner,
                    SubscriptionIdentity(normalizedMarket, normalizedCode, quoteType),
                )
            )
        }
        val added = increment(normalizedMarket, normalizedCode, newlyOwned)
        if (added.isNotEmpty()) {
            client.connect()
            client.subscribe(normalizedMarket, normalizedCode, added)
        }
    }

    @Synchronized
    fun releaseCurrentView(owner: String, market: String, code: String) {
        val normalizedMarket = market.uppercase()
        val normalizedCode = code.uppercase()
        val released = RealtimeQuoteType.entries.filterTo(mutableSetOf()) { quoteType ->
            ownerSubscriptions.remove(
                OwnerIdentity(
                    owner,
                    SubscriptionIdentity(normalizedMarket, normalizedCode, quoteType),
                )
            )
        }
        val removed = decrement(normalizedMarket, normalizedCode, released)
        if (removed.isNotEmpty()) {
            client.unsubscribe(normalizedMarket, normalizedCode, removed)
        }
    }

    fun getQuoteState(market: String, code: String): RealtimeQuote? {
        val key = "${market.uppercase()}:${code.uppercase()}"
        val map: Map<String, RealtimeQuote> = _latestQuotes.value
        return map[key]
    }

    private fun increment(
        market: String,
        code: String,
        quoteTypes: Set<RealtimeQuoteType>,
    ): Set<RealtimeQuoteType> {
        val added = mutableSetOf<RealtimeQuoteType>()
        quoteTypes.forEach { quoteType ->
            val identity = SubscriptionIdentity(market.uppercase(), code.uppercase(), quoteType)
            val count = refCounts.getOrDefault(identity, 0)
            refCounts[identity] = count + 1
            if (count == 0) added.add(quoteType)
        }
        return added
    }

    private fun decrement(
        market: String,
        code: String,
        quoteTypes: Set<RealtimeQuoteType>,
    ): Set<RealtimeQuoteType> {
        val removed = mutableSetOf<RealtimeQuoteType>()
        quoteTypes.forEach { quoteType ->
            val identity = SubscriptionIdentity(market.uppercase(), code.uppercase(), quoteType)
            val count = refCounts.getOrDefault(identity, 0)
            when {
                count <= 0 -> Unit
                count == 1 -> {
                    refCounts.remove(identity)
                    removed.add(quoteType)
                }
                else -> refCounts[identity] = count - 1
            }
        }
        return removed
    }
}
