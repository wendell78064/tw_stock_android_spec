package tw.market.ledger.network

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import tw.market.ledger.model.RealtimeConnectionState
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeQuote
import tw.market.ledger.model.RealtimeTradingSession
import tw.market.ledger.model.IntradayCandle
import tw.market.ledger.model.IntradayInterval
import kotlin.math.min
import kotlin.math.pow

enum class RealtimeQuoteType(val wireValue: String) {
    TICK("tick"),
    BID_ASK("bid_ask"),
}

data class RealtimeSubscriptionTarget(
    val market: String,
    val code: String,
    val quoteType: RealtimeQuoteType,
)

interface RealtimeSubscriptionClient {
    val quotesFlow: SharedFlow<RealtimeQuote>
    fun connect()
    fun subscribe(market: String, code: String, quoteTypes: Set<RealtimeQuoteType>)
    fun unsubscribe(market: String, code: String, quoteTypes: Set<RealtimeQuoteType>)
}

class RealtimeQuoteClient(
    private val okHttpClient: OkHttpClient,
    val serverUrl: String
) : RealtimeSubscriptionClient {
    private val scope = CoroutineScope(Dispatchers.IO + Job())
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()

    private val _connectionState = MutableStateFlow(RealtimeConnectionState.DISCONNECTED)
    val connectionState: StateFlow<RealtimeConnectionState> = _connectionState.asStateFlow()

    private val _quotesFlow = MutableSharedFlow<RealtimeQuote>(extraBufferCapacity = 64)
    override val quotesFlow: SharedFlow<RealtimeQuote> = _quotesFlow.asSharedFlow()
    private val _candlesFlow = MutableSharedFlow<IntradayCandle>(extraBufferCapacity = 64)
    val candlesFlow: SharedFlow<IntradayCandle> = _candlesFlow.asSharedFlow()
    private val _aggregateUpdates = MutableSharedFlow<String>(extraBufferCapacity = 16)
    val aggregateUpdates: SharedFlow<String> = _aggregateUpdates.asSharedFlow()
    private val globalChannels = mutableSetOf<String>()

    private var webSocket: WebSocket? = null
    private val subscribedTargets = mutableSetOf<RealtimeSubscriptionTarget>()
    private var reconnectAttempt = 0
    private var isExplicitDisconnect = false

    override fun connect() {
        isExplicitDisconnect = false
        if (_connectionState.value == RealtimeConnectionState.CONNECTED || _connectionState.value == RealtimeConnectionState.CONNECTING) {
            return
        }
        _connectionState.value = RealtimeConnectionState.CONNECTING

        val request = Request.Builder().url(serverUrl).build()
        webSocket = okHttpClient.newWebSocket(request, createWebSocketListener())
    }

    fun disconnect() {
        isExplicitDisconnect = true
        webSocket?.close(1000, "App disconnect requested")
        webSocket = null
        _connectionState.value = RealtimeConnectionState.DISCONNECTED
    }

    @Synchronized
    override fun subscribe(
        market: String,
        code: String,
        quoteTypes: Set<RealtimeQuoteType>,
    ) {
        val normalizedMarket = market.uppercase()
        val normalizedCode = code.uppercase()
        val added = quoteTypes.filterTo(mutableSetOf()) { quoteType ->
            subscribedTargets.add(
                RealtimeSubscriptionTarget(normalizedMarket, normalizedCode, quoteType)
            )
        }
        if (added.isNotEmpty() && _connectionState.value == RealtimeConnectionState.CONNECTED) {
            sendSubscriptionMessage(
                "subscribe",
                targets(normalizedMarket, normalizedCode, added),
            )
        }
    }

    @Synchronized
    override fun unsubscribe(
        market: String,
        code: String,
        quoteTypes: Set<RealtimeQuoteType>,
    ) {
        val normalizedMarket = market.uppercase()
        val normalizedCode = code.uppercase()
        val removed = quoteTypes.filterTo(mutableSetOf()) { quoteType ->
            subscribedTargets.remove(
                RealtimeSubscriptionTarget(normalizedMarket, normalizedCode, quoteType)
            )
        }
        if (removed.isNotEmpty() && _connectionState.value == RealtimeConnectionState.CONNECTED) {
            sendSubscriptionMessage(
                "unsubscribe",
                targets(normalizedMarket, normalizedCode, removed),
            )
        }
    }

    fun subscribeChannels(vararg channels: String) {
        globalChannels.addAll(channels)
        connect()
        if (_connectionState.value == RealtimeConnectionState.CONNECTED) {
            sendSubscriptionMessage("subscribe", emptyList())
        }
    }

    private fun sendSubscriptionMessage(type: String, targets: List<Map<String, Any>>) {
        val payload = mapOf(
            "type" to type,
            "version" to 1,
            "securities" to targets,
            "channels" to (listOf("quote", "candle_1m", "candle_5m") + globalChannels).distinct()
        )
        val json = moshi.adapter(Map::class.java).toJson(payload)
        webSocket?.send(json)
    }

    @Synchronized
    private fun resubscribeAll() {
        val targets = activeSubscriptionTargets()
        if (targets.isNotEmpty()) {
            sendSubscriptionMessage("subscribe", targets)
        }
    }

    @Synchronized
    internal fun activeSubscriptionTargets(): List<Map<String, Any>> = subscribedTargets
        .groupBy { it.market to it.code }
        .map { (security, rows) ->
            mapOf(
                "market" to security.first,
                "code" to security.second,
                "quote_types" to rows.map { it.quoteType.wireValue }.sorted(),
            )
        }

    private fun targets(
        market: String,
        code: String,
        quoteTypes: Set<RealtimeQuoteType>,
    ): List<Map<String, Any>> = listOf(
        mapOf(
            "market" to market,
            "code" to code,
            "quote_types" to quoteTypes.map { it.wireValue }.sorted(),
        )
    )

    private fun scheduleReconnect() {
        if (isExplicitDisconnect) return
        _connectionState.value = RealtimeConnectionState.RECONNECTING
        reconnectAttempt++

        val backoffSeconds = min(30.0, 2.0.pow(reconnectAttempt.toDouble())).toLong()
        scope.launch {
            delay(backoffSeconds * 1000)
            if (!isExplicitDisconnect) {
                connect()
            }
        }
    }

    private fun createWebSocketListener() = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            _connectionState.value = RealtimeConnectionState.CONNECTED
            reconnectAttempt = 0
            resubscribeAll()
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            try {
                val mapAdapter = moshi.adapter(Map::class.java)
                val msg = mapAdapter.fromJson(text) ?: return
                val type = msg["type"] as? String ?: return

                if (type == "quote" || type == "snapshot") {
                    val data = msg["data"] as? Map<*, *> ?: return
                    val q = parseQuoteMap(data)
                    if (q != null) {
                        _quotesFlow.tryEmit(q)
                    }
                } else if (type == "candle") {
                    (msg["data"] as? Map<*, *>)?.let(::parseCandleMap)?.let(_candlesFlow::tryEmit)
                } else if (type == "candle_snapshot") {
                    (msg["data"] as? List<*>)?.forEach { row ->
                        (row as? Map<*, *>)?.let(::parseCandleMap)?.let(_candlesFlow::tryEmit)
                    }
                } else if (type in setOf("market_snapshot", "market_update", "taxonomy_ranking_snapshot", "taxonomy_ranking_update", "taxonomy_detail_update", "alert_event", "alert_status")) {
                    _aggregateUpdates.tryEmit(type)
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            _connectionState.value = RealtimeConnectionState.UNAVAILABLE
            scheduleReconnect()
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            _connectionState.value = RealtimeConnectionState.DISCONNECTED
            if (!isExplicitDisconnect) {
                scheduleReconnect()
            }
        }
    }

    private fun parseQuoteMap(m: Map<*, *>): RealtimeQuote? {
        return try {
            RealtimeQuote(
                securityId = m["security_id"].toString(),
                marketId = m["market_id"].toString(),
                code = m["code"].toString(),
                exchangeTimestamp = m["exchange_timestamp"].toString(),
                receivedAt = m["received_at"].toString(),
                lastPrice = m["last_price"].toString(),
                lastSize = (m["last_size"] as? Number)?.toInt() ?: 0,
                openPrice = m["open_price"]?.toString(),
                highPrice = m["high_price"]?.toString(),
                lowPrice = m["low_price"]?.toString(),
                previousClose = m["previous_close"]?.toString(),
                totalVolume = (m["total_volume"] as? Number)?.toLong() ?: 0L,
                turnoverAmount = m["turnover_amount"]?.toString(),
                bidPrice = m["bid_price"]?.toString(),
                bidSize = (m["bid_size"] as? Number)?.toInt(),
                askPrice = m["ask_price"]?.toString(),
                askSize = (m["ask_size"] as? Number)?.toInt(),
                change = m["change"]?.toString(),
                changePercent = m["change_percent"]?.toString(),
                session = RealtimeTradingSession.valueOf(m["session"]?.toString() ?: "REGULAR"),
                sequence = (m["sequence"] as? Number)?.toLong(),
                dataStatus = RealtimeDataStatus.valueOf(m["data_status"]?.toString() ?: "LIVE"),
                provider = m["provider"]?.toString() ?: "UNKNOWN",
                delaySeconds = (m["delay_seconds"] as? Number)?.toInt() ?: 0
            )
        } catch (e: Exception) {
            null
        }
    }

    private fun parseCandleMap(m: Map<*, *>): IntradayCandle? = try {
        IntradayCandle(
            securityId = m["security_id"].toString(), marketId = m["market_id"].toString(),
            code = m["code"].toString(), interval = IntradayInterval.entries.first { it.apiValue == m["interval"] },
            session = RealtimeTradingSession.valueOf(m["session"].toString()), bucketStart = m["bucket_start"].toString(),
            bucketEnd = m["bucket_end"].toString(), open = m["open"].toString(), high = m["high"].toString(),
            low = m["low"].toString(), close = m["close"].toString(), volume = (m["volume"] as Number).toLong(),
            turnoverAmount = m["turnover_amount"]?.toString(), quoteCount = (m["quote_count"] as Number).toInt(),
            isFinal = m["is_final"] as? Boolean ?: false,
            dataStatus = RealtimeDataStatus.valueOf(m["data_status"]?.toString() ?: "UNAVAILABLE"),
            provider = m["provider"]?.toString() ?: "UNKNOWN", updatedAt = m["updated_at"].toString(),
        )
    } catch (_: Exception) { null }
}
