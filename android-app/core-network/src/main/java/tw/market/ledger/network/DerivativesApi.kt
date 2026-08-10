package tw.market.ledger.network

import com.squareup.moshi.Json
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

data class FuturesProductDto(val code: String, val name: String,
    @Json(name="contract_multiplier") val contractMultiplier: String, val currency: String,
    @Json(name="is_active") val isActive: Boolean)
data class FuturesQuoteDto(@Json(name="contract_code") val contractCode: String,
    @Json(name="contract_month") val contractMonth: String, @Json(name="trade_date") val tradeDate: String,
    val open: String?, val high: String?, val low: String?, val close: String?,
    @Json(name="settlement_price") val settlementPrice: String?, val change: String?,
    @Json(name="change_percent") val changePercent: String?, val volume: Long?,
    @Json(name="open_interest") val openInterest: Long?, @Json(name="close_basis") val closeBasis: String?,
    @Json(name="data_status") val dataStatus: String, @Json(name="as_of") val asOf: String)
data class FuturesOverviewDto(val product: FuturesProductDto, val near: FuturesQuoteDto?,
    val next: FuturesQuoteDto?, @Json(name="data_status") val dataStatus: String)
data class FuturesOverviewEnvelopeDto(val data: FuturesOverviewDto)
data class FuturesPositionDto(@Json(name="trade_date") val tradeDate: String,
    @Json(name="institution_type") val institutionType: String,
    @Json(name="long_oi") val longOi: Long?, @Json(name="short_oi") val shortOi: Long?,
    @Json(name="net_oi") val netOi: Long?, @Json(name="net_oi_change") val netOiChange: Long?,
    @Json(name="data_status") val dataStatus: String)
data class FuturesPositionsEnvelopeDto(val data: List<FuturesPositionDto>)
data class ContinuousPointDto(@Json(name="trade_date") val tradeDate: String, val open: String?,
    val high: String?, val low: String?, val close: String?, val volume: Long?,
    @Json(name="open_interest") val openInterest: Long?, @Json(name="source_contract") val sourceContract: String,
    @Json(name="roll_date") val rollDate: String?, @Json(name="roll_method") val rollMethod: String)
data class ContinuousEnvelopeDto(val data: List<ContinuousPointDto>)

interface DerivativesApi {
    @GET("futures/products/{product}/overview") suspend fun overview(@Path("product") product: String): FuturesOverviewEnvelopeDto
    @GET("futures/products/{product}/institutional-positions") suspend fun positions(
        @Path("product") product: String, @Query("window") window: Int): FuturesPositionsEnvelopeDto
    @GET("futures/products/{product}/continuous-candles") suspend fun continuous(
        @Path("product") product: String, @Query("range") range: String,
        @Query("roll_method") rollMethod: String): ContinuousEnvelopeDto
}
