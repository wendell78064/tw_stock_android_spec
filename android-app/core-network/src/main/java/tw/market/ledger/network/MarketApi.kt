package tw.market.ledger.network

import com.squareup.moshi.Json
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

data class MarketIndexDto(val code: String, val name: String, val market: String,
    @Json(name="trade_date") val tradeDate: String, val open: String?, val high: String?,
    val low: String?, val close: String?, val change: String?,
    @Json(name="change_percent") val changePercent: String?,
    @Json(name="turnover_amount") val turnoverAmount: String?, val volume: Long?,
    @Json(name="as_of") val asOf: String, @Json(name="data_status") val dataStatus: String)
data class MarketBreadthDto(val market: String, @Json(name="trade_date") val tradeDate: String,
    val advancers: Int?, val decliners: Int?, val unchanged: Int?,
    @Json(name="limit_up") val limitUp: Int?, @Json(name="limit_down") val limitDown: Int?,
    @Json(name="total_traded") val totalTraded: Int?,
    @Json(name="turnover_amount") val turnoverAmount: String?, @Json(name="as_of") val asOf: String,
    @Json(name="data_status") val dataStatus: String)
data class InstitutionalPointDto(val market: String, @Json(name="security_code") val securityCode: String?,
    @Json(name="trade_date") val tradeDate: String, @Json(name="institution_type") val institutionType: String,
    @Json(name="dealer_subtype") val dealerSubtype: String?, val buy: String?, val sell: String?,
    val net: String?, @Json(name="cumulative_net") val cumulativeNet: String?,
    @Json(name="consecutive_direction_days") val consecutiveDirectionDays: Int,
    @Json(name="as_of") val asOf: String, @Json(name="data_status") val dataStatus: String)
data class MarginPointDto(@Json(name="trade_date") val tradeDate: String,
    @Json(name="margin_balance") val marginBalance: Long?, @Json(name="margin_balance_change") val marginBalanceChange: Long?,
    @Json(name="short_balance") val shortBalance: Long?, @Json(name="short_balance_change") val shortBalanceChange: Long?,
    @Json(name="short_margin_ratio") val shortMarginRatio: String?, @Json(name="as_of") val asOf: String,
    @Json(name="data_status") val dataStatus: String)
data class LendingPointDto(@Json(name="trade_date") val tradeDate: String,
    @Json(name="lending_sell") val lendingSell: Long?, @Json(name="lending_balance") val lendingBalance: Long?,
    @Json(name="lending_balance_change") val lendingBalanceChange: Long?, @Json(name="as_of") val asOf: String,
    @Json(name="data_status") val dataStatus: String)
data class MarketOverviewDataDto(val indexes: List<MarketIndexDto>, val breadth: List<MarketBreadthDto>,
    @Json(name="institutional_spot") val institutionalSpot: List<InstitutionalPointDto>,
    val credit: List<MarginPointDto>, val lending: List<LendingPointDto>)
data class SpotMetaDto(@Json(name="data_status") val dataStatus: String, @Json(name="as_of") val asOf: String?)
data class MarketOverviewEnvelopeDto(val data: MarketOverviewDataDto, val meta: SpotMetaDto)
data class InstitutionalEnvelopeDto(val data: List<InstitutionalPointDto>)
data class CreditDataDto(val margin: List<MarginPointDto>, val lending: List<LendingPointDto>)
data class CreditEnvelopeDto(val data: CreditDataDto)

interface MarketApi {
    @GET("market/overview") suspend fun overview(): MarketOverviewEnvelopeDto
    @GET("market/institutional/spot") suspend fun marketInstitutional(@Query("market") market: String,
        @Query("window") window: Int): InstitutionalEnvelopeDto
    @GET("securities/{code}/institutional") suspend fun securityInstitutional(@Path("code") code: String,
        @Query("market") market: String, @Query("window") window: Int): InstitutionalEnvelopeDto
    @GET("securities/{code}/credit") suspend fun securityCredit(@Path("code") code: String,
        @Query("market") market: String, @Query("window") window: Int): CreditEnvelopeDto
}
