package tw.market.ledger.network

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.model.RealtimeQuote

data class RealtimeSecurityTarget(
    val market: String,
    val code: String,
)

data class PortfolioMembershipUpdate(
    val enabled: Boolean,
    val added: Set<RealtimeSecurityTarget> = emptySet(),
    val removed: Set<RealtimeSecurityTarget> = emptySet(),
    val rejected: Set<RealtimeSecurityTarget> = emptySet(),
)

data class WatchlistMembershipUpdate(
    val enabled: Boolean,
    val added: Set<RealtimeSecurityTarget> = emptySet(),
    val removed: Set<RealtimeSecurityTarget> = emptySet(),
    val rejected: Set<RealtimeSecurityTarget> = emptySet(),
)

data class IndustryMembershipUpdate(
    val enabled: Boolean,
    val added: Set<RealtimeSecurityTarget> = emptySet(),
    val removed: Set<RealtimeSecurityTarget> = emptySet(),
    val rejected: Set<RealtimeSecurityTarget> = emptySet(),
)

class RealtimeSubscriptionManager(
    private val client: RealtimeSubscriptionClient,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO + Job()),
    private val portfolioRealtimeEnabled: Boolean = false,
    private val watchlistRealtimeEnabled: Boolean = false,
    private val industryRealtimeEnabled: Boolean = false,
) {
    companion object {
        const val P0_PORTFOLIO_OWNER = "P0_PORTFOLIO"
        const val P3_INDUSTRY_OWNER = "P3_INDUSTRY"
        const val P4_WATCHLIST_OWNER = "P4_WATCHLIST"
    }

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
    private var portfolioTargets = emptySet<RealtimeSecurityTarget>()
    private var watchlistTargets = emptySet<RealtimeSecurityTarget>()
    private var industryTargets = emptySet<RealtimeSecurityTarget>()

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

    @Synchronized
    fun updatePortfolioMembership(
        targets: Set<RealtimeSecurityTarget>,
    ): PortfolioMembershipUpdate {
        val normalized = targets.mapTo(mutableSetOf()) {
            RealtimeSecurityTarget(it.market.uppercase(), it.code.uppercase())
        }
        val rejected = normalized.filterNotTo(mutableSetOf(), ::isValidPortfolioTarget)
        if (!portfolioRealtimeEnabled) {
            return PortfolioMembershipUpdate(enabled = false, rejected = rejected)
        }
        val current = portfolioTargets
        val next = normalized - rejected
        val removed = current - next
        val added = next - current

        removed.sortedWith(compareBy({ it.market }, { it.code })).forEach { target ->
            val identity = SubscriptionIdentity(target.market, target.code, RealtimeQuoteType.TICK)
            if (ownerSubscriptions.remove(OwnerIdentity(P0_PORTFOLIO_OWNER, identity))) {
                val brokerRemoved = decrement(
                    target.market,
                    target.code,
                    setOf(RealtimeQuoteType.TICK),
                )
                if (brokerRemoved.isNotEmpty()) {
                    client.unsubscribe(target.market, target.code, brokerRemoved)
                }
            }
        }

        var connectRequired = false
        added.sortedWith(compareBy({ it.market }, { it.code })).forEach { target ->
            val identity = SubscriptionIdentity(target.market, target.code, RealtimeQuoteType.TICK)
            if (ownerSubscriptions.add(OwnerIdentity(P0_PORTFOLIO_OWNER, identity))) {
                val brokerAdded = increment(
                    target.market,
                    target.code,
                    setOf(RealtimeQuoteType.TICK),
                )
                if (brokerAdded.isNotEmpty()) {
                    client.subscribe(target.market, target.code, brokerAdded)
                    connectRequired = true
                }
            }
        }
        if (connectRequired) client.connect()
        portfolioTargets = next
        return PortfolioMembershipUpdate(
            enabled = true,
            added = added,
            removed = removed,
            rejected = rejected,
        )
    }

    @Synchronized
    fun releasePortfolioMembership(): PortfolioMembershipUpdate =
        updatePortfolioMembership(emptySet())

    @Synchronized
    fun updateWatchlistMembership(
        targets: Set<RealtimeSecurityTarget>,
    ): WatchlistMembershipUpdate {
        val normalized = targets.mapTo(mutableSetOf()) {
            RealtimeSecurityTarget(it.market.uppercase(), it.code.uppercase())
        }
        val rejected = normalized.filterNotTo(mutableSetOf(), ::isValidTarget)
        if (!watchlistRealtimeEnabled) {
            return WatchlistMembershipUpdate(enabled = false, rejected = rejected)
        }
        val current = watchlistTargets
        val next = normalized - rejected
        val removed = current - next
        val added = next - current

        updateTickOwnership(P4_WATCHLIST_OWNER, removed, acquire = false)
        updateTickOwnership(P4_WATCHLIST_OWNER, added, acquire = true)
        watchlistTargets = next
        return WatchlistMembershipUpdate(
            enabled = true,
            added = added,
            removed = removed,
            rejected = rejected,
        )
    }

    @Synchronized
    fun releaseWatchlistMembership(): WatchlistMembershipUpdate =
        updateWatchlistMembership(emptySet())

    @Synchronized
    fun updateIndustryMembership(
        targets: Set<RealtimeSecurityTarget>,
    ): IndustryMembershipUpdate {
        val normalized = targets.mapTo(mutableSetOf()) {
            RealtimeSecurityTarget(it.market.uppercase(), it.code.uppercase())
        }
        val rejected = normalized.filterNotTo(mutableSetOf(), ::isValidTarget)
        if (!industryRealtimeEnabled) {
            return IndustryMembershipUpdate(enabled = false, rejected = rejected)
        }
        val current = industryTargets
        val next = normalized - rejected
        val removed = current - next
        val added = next - current

        updateTickOwnership(P3_INDUSTRY_OWNER, removed, acquire = false)
        updateTickOwnership(P3_INDUSTRY_OWNER, added, acquire = true)
        industryTargets = next
        return IndustryMembershipUpdate(
            enabled = true,
            added = added,
            removed = removed,
            rejected = rejected,
        )
    }

    @Synchronized
    fun releaseIndustryMembership(): IndustryMembershipUpdate =
        updateIndustryMembership(emptySet())

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

    private fun updateTickOwnership(
        owner: String,
        targets: Set<RealtimeSecurityTarget>,
        acquire: Boolean,
    ) {
        var connectRequired = false
        targets.sortedWith(compareBy({ it.market }, { it.code })).forEach { target ->
            val identity = SubscriptionIdentity(target.market, target.code, RealtimeQuoteType.TICK)
            if (acquire && ownerSubscriptions.add(OwnerIdentity(owner, identity))) {
                val added = increment(target.market, target.code, setOf(RealtimeQuoteType.TICK))
                if (added.isNotEmpty()) {
                    client.subscribe(target.market, target.code, added)
                    connectRequired = true
                }
            } else if (!acquire && ownerSubscriptions.remove(OwnerIdentity(owner, identity))) {
                val removed = decrement(target.market, target.code, setOf(RealtimeQuoteType.TICK))
                if (removed.isNotEmpty()) client.unsubscribe(target.market, target.code, removed)
            }
        }
        if (connectRequired) client.connect()
    }

    private fun isValidPortfolioTarget(target: RealtimeSecurityTarget): Boolean = isValidTarget(target)

    private fun isValidTarget(target: RealtimeSecurityTarget): Boolean =
        target.market in setOf("TWSE", "TPEX") && target.code.matches(Regex("^[0-9]{4,6}$"))
}
