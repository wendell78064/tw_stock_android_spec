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
    private val client: RealtimeQuoteClient
) {
    private val scope = CoroutineScope(Dispatchers.IO + Job())

    // Reference counter for securities: "MARKET:CODE" -> Count
    private val refCounts = mutableMapOf<String, Int>()

    // Latest quote cache: "MARKET:CODE" -> RealtimeQuote
    private val _latestQuotes = MutableStateFlow<Map<String, RealtimeQuote>>(emptyMap())
    val latestQuotes: StateFlow<Map<String, RealtimeQuote>> = _latestQuotes.asStateFlow()

    init {
        scope.launch {
            client.quotesFlow.collect { quote ->
                val current = _latestQuotes.value.toMutableMap()
                current[quote.compositeKey] = quote
                _latestQuotes.value = current
            }
        }
    }

    fun subscribe(market: String, code: String) {
        val key = "${market.uppercase()}:${code.uppercase()}"
        val count = refCounts.getOrDefault(key, 0)
        refCounts[key] = count + 1

        if (count == 0) {
            client.connect()
            client.subscribe(market, code)
        }
    }

    fun unsubscribe(market: String, code: String) {
        val key = "${market.uppercase()}:${code.uppercase()}"
        val count = refCounts.getOrDefault(key, 0)
        if (count <= 1) {
            refCounts.remove(key)
            client.unsubscribe(market, code)
        } else {
            refCounts[key] = count - 1
        }
    }

    fun getQuoteState(market: String, code: String): RealtimeQuote? {
        return _latestQuotes.value["${market.uppercase()}:${code.uppercase()}"]
    }
}
