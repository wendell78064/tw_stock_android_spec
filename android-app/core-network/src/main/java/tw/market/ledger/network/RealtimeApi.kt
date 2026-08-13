package tw.market.ledger.network

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

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

interface RealtimeApi {
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
