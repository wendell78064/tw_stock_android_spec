package tw.market.ledger.network

import com.squareup.moshi.Json
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

data class CandleDto(
    val time: String,
    val open: String,
    val high: String,
    val low: String,
    val close: String,
    @Json(name = "volume_shares") val volumeShares: Long?,
    @Json(name = "turnover_amount") val turnoverAmount: String?,
)

data class CandleEnvelopeDto(
    val data: List<CandleDto>,
    val meta: MetaDto,
    val interval: String,
    val adjustment: String,
    @Json(name = "display_note") val displayNote: String?,
)

data class IndicatorValueDto(val name: String, val value: String?)
data class TechnicalPointDto(
    @Json(name = "trade_date") val tradeDate: String,
    @Json(name = "price_basis") val priceBasis: String,
    @Json(name = "algorithm_version") val algorithmVersion: String,
    val indicators: List<IndicatorValueDto>,
    @Json(name = "as_of") val asOf: String,
    @Json(name = "data_status") val dataStatus: String,
)
data class TechnicalEnvelopeDto(val data: List<TechnicalPointDto>, val meta: MetaDto)

interface ChartApi {
    @GET("securities/{code}/candles")
    suspend fun candles(
        @Path("code") code: String,
        @Query("market") market: String,
        @Query("range") range: String,
        @Query("interval") interval: String,
        @Query("adjustment") adjustment: String,
    ): CandleEnvelopeDto

    @GET("securities/{code}/technicals")
    suspend fun technicals(
        @Path("code") code: String,
        @Query("market") market: String,
        @Query("price_basis") basis: String,
        @Query("indicators") indicators: String,
    ): TechnicalEnvelopeDto
}
