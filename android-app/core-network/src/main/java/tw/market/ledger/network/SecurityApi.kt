package tw.market.ledger.network

import com.squareup.moshi.Json
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

data class MetaDto(
    @Json(name = "as_of") val asOf: String,
    @Json(name = "received_at") val receivedAt: String,
    @Json(name = "data_status") val dataStatus: String,
    val source: String,
)

data class SecurityDto(
    val id: String,
    val code: String,
    val name: String,
    val market: String,
    @Json(name = "security_type") val securityType: String,
    val status: String? = null,
    @Json(name = "primary_industry") val primaryIndustry: String? = null,
    @Json(name = "listing_date") val listingDate: String? = null,
    @Json(name = "is_active") val isActive: Boolean,
    @Json(name = "as_of") val asOf: String,
    @Json(name = "received_at") val receivedAt: String,
    @Json(name = "data_status") val dataStatus: String,
)

data class SecuritySearchEnvelopeDto(val data: List<SecurityDto>, val meta: MetaDto)
data class SecurityEnvelopeDto(val data: SecurityDto, val meta: MetaDto)

interface SecurityApi {
    @GET("securities/search")
    suspend fun search(
        @Query("q") query: String,
        @Query("market") market: String? = null,
        @Query("type") type: String = "COMMON_STOCK",
        @Query("limit") limit: Int = 20,
    ): SecuritySearchEnvelopeDto

    @GET("securities/{code}")
    suspend fun detail(
        @Path("code") code: String,
        @Query("market") market: String,
    ): SecurityEnvelopeDto
}

