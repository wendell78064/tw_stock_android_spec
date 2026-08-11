package tw.market.ledger.network

import com.squareup.moshi.Json
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path

data class WatchlistDto(val id: String, val name: String, @Json(name = "sort_order") val sortOrder: Int)
data class WatchlistEnvelope(val data: WatchlistDto)
data class WatchlistListEnvelope(val data: List<WatchlistDto>)
data class WatchlistItemDto(
    val id: String,
    @Json(name = "watchlist_id") val watchlistId: String,
    @Json(name = "security_code") val securityCode: String,
    @Json(name = "security_name") val securityName: String,
    val market: String,
    @Json(name = "sort_order") val sortOrder: Int,
    val note: String? = null,
    @Json(name = "target_price") val targetPrice: String? = null,
    @Json(name = "stop_price") val stopPrice: String? = null,
    @Json(name = "add_price") val addPrice: String? = null,
    val close: String? = null,
    val change: String? = null,
    @Json(name = "change_percent") val changePercent: String? = null,
    @Json(name = "price_as_of") val priceAsOf: String? = null,
    @Json(name = "data_status") val dataStatus: String = "UNAVAILABLE",
    @Json(name = "foreign_net") val foreignNet: Long? = null,
    @Json(name = "margin_balance_change") val marginBalanceChange: Long? = null,
    @Json(name = "price_above_ma20") val priceAboveMa20: Boolean? = null,
)
data class WatchlistItemEnvelope(val data: WatchlistItemDto)
data class WatchlistItemListEnvelope(val data: List<WatchlistItemDto>)
data class WatchlistNameInput(val name: String)
data class WatchlistAddInput(@Json(name = "security_code") val securityCode: String, val market: String? = null)
data class WatchlistItemInput(
    val note: String?,
    @Json(name = "target_price") val targetPrice: String?,
    @Json(name = "stop_price") val stopPrice: String?,
    @Json(name = "add_price") val addPrice: String?,
)
data class WatchlistOrderInput(val id: String, @Json(name = "sort_order") val sortOrder: Int)

interface WatchlistApi {
    @GET("watchlists") suspend fun groups(): WatchlistListEnvelope
    @POST("watchlists") suspend fun create(@Body input: WatchlistNameInput): WatchlistEnvelope
    @PATCH("watchlists/{id}") suspend fun rename(@Path("id") id: String, @Body input: WatchlistNameInput): WatchlistEnvelope
    @DELETE("watchlists/{id}") suspend fun delete(@Path("id") id: String)
    @PUT("watchlists/reorder") suspend fun reorderGroups(@Body input: List<WatchlistOrderInput>): WatchlistListEnvelope
    @POST("watchlists/{id}/items") suspend fun add(@Path("id") id: String, @Body input: WatchlistAddInput): WatchlistItemEnvelope
    @PATCH("watchlists/{id}/items/{item}") suspend fun edit(@Path("id") id: String, @Path("item") item: String, @Body input: WatchlistItemInput): WatchlistItemEnvelope
    @DELETE("watchlists/{id}/items/{item}") suspend fun remove(@Path("id") id: String, @Path("item") item: String)
    @PUT("watchlists/{id}/items/reorder") suspend fun reorderItems(@Path("id") id: String, @Body input: List<WatchlistOrderInput>): WatchlistItemListEnvelope
    @GET("watchlists/{id}/overview") suspend fun overview(@Path("id") id: String): WatchlistItemListEnvelope
}
