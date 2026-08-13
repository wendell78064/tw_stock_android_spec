package tw.market.ledger.network

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

@JsonClass(generateAdapter = true)
data class RealtimeQuoteDto(
    @Json(name = "security_id") val securityId: String,
    @Json(name = "market_id") val marketId: String,
    @Json(name = "code") val code: String,
    @Json(name = "exchange_timestamp") val exchangeTimestamp: String,
    @Json(name = "received_at") val receivedAt: String,
    @Json(name = "last_price") val lastPrice: String,
    @Json(name = "last_size") val lastSize: Int = 0,
    @Json(name = "open_price") val openPrice: String? = null,
    @Json(name = "high_price") val highPrice: String? = null,
    @Json(name = "low_price") val lowPrice: String? = null,
    @Json(name = "previous_close") val previousClose: String? = null,
    @Json(name = "total_volume") val totalVolume: Long = 0,
    @Json(name = "turnover_amount") val turnoverAmount: String? = null,
    @Json(name = "bid_price") val bidPrice: String? = null,
    @Json(name = "bid_size") val bidSize: Int? = null,
    @Json(name = "ask_price") val askPrice: String? = null,
    @Json(name = "ask_size") val askSize: Int? = null,
    @Json(name = "change") val change: String? = null,
    @Json(name = "change_percent") val changePercent: String? = null,
    @Json(name = "session") val session: String = "REGULAR",
    @Json(name = "sequence") val sequence: Long? = null,
    @Json(name = "data_status") val dataStatus: String = "LIVE",
    @Json(name = "provider") val provider: String = "UNKNOWN",
    @Json(name = "delay_seconds") val delaySeconds: Int = 0
)

@JsonClass(generateAdapter = true)
data class BatchQuoteTargetDto(
    @Json(name = "market") val market: String,
    @Json(name = "code") val code: String
)

@JsonClass(generateAdapter = true)
data class BatchQuoteRequestDto(
    @Json(name = "targets") val targets: List<BatchQuoteTargetDto>
)

@JsonClass(generateAdapter = true)
data class IntradayCandleDto(
    @Json(name = "security_id") val securityId: String,
    @Json(name = "market_id") val marketId: String,
    val code: String,
    val interval: String,
    val session: String,
    @Json(name = "bucket_start") val bucketStart: String,
    @Json(name = "bucket_end") val bucketEnd: String,
    val open: String,
    val high: String,
    val low: String,
    val close: String,
    val volume: Long,
    @Json(name = "turnover_amount") val turnoverAmount: String?,
    @Json(name = "quote_count") val quoteCount: Int,
    @Json(name = "is_final") val isFinal: Boolean,
    @Json(name = "data_status") val dataStatus: String,
    val provider: String,
    @Json(name = "updated_at") val updatedAt: String,
)

@JsonClass(generateAdapter = true)
data class IntradayCandleEnvelopeDto(
    val interval: String,
    val candles: List<IntradayCandleDto>,
    @Json(name = "data_status") val dataStatus: String,
    @Json(name = "as_of") val asOf: String,
    val provider: String,
)

interface RealtimeApi {
    @GET("v1/intraday/{market}/{code}/candles")
    suspend fun getIntradayCandles(
        @Path("market") market: String,
        @Path("code") code: String,
        @Query("interval") interval: String,
        @Query("limit") limit: Int = 500,
    ): Response<IntradayCandleEnvelopeDto>
    @GET("v1/quotes/{market}/{code}")
    suspend fun getLatestQuote(
        @Path("market") market: String,
        @Path("code") code: String
    ): Response<RealtimeQuoteDto>

    @POST("v1/quotes/batch")
    suspend fun getQuotesBatch(
        @Body request: BatchQuoteRequestDto
    ): Response<List<RealtimeQuoteDto?>>
}
