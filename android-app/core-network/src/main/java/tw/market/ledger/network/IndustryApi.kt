package tw.market.ledger.network

import com.squareup.moshi.Json
import retrofit2.http.GET
import retrofit2.http.Path

data class IndustryDto(
    val id: String,
    val code: String,
    val name: String,
    @Json(name = "classification_source") val classificationSource: String,
    @Json(name = "member_count") val memberCount: Int = 0,
)

data class ThemeDto(
    val id: String,
    val code: String,
    val name: String,
    val description: String? = null,
    @Json(name = "classification_type") val classificationType: String,
    @Json(name = "member_count") val memberCount: Int = 0,
    @Json(name = "created_at") val createdAt: String? = null,
    @Json(name = "updated_at") val updatedAt: String? = null,
)

data class MemberSecurityDto(
    @Json(name = "security_id") val securityId: String,
    val code: String,
    val name: String,
    val market: String,
    @Json(name = "security_type") val securityType: String = "COMMON_STOCK",
    @Json(name = "is_active") val isActive: Boolean = true,
    val close: String? = null,
    val change: String? = null,
    @Json(name = "change_percent") val changePercent: String? = null,
    @Json(name = "as_of") val asOf: String? = null,
    @Json(name = "data_status") val dataStatus: String,
)

data class IndustryListEnvelopeDto(val data: List<IndustryDto>, val meta: MetaDto)
data class IndustryEnvelopeDto(val data: IndustryDto, val meta: MetaDto)
data class IndustrySecuritiesEnvelopeDto(val data: List<MemberSecurityDto>, val meta: MetaDto)

data class ThemeListEnvelopeDto(val data: List<ThemeDto>, val meta: MetaDto)
data class ThemeEnvelopeDto(val data: ThemeDto, val meta: MetaDto)
data class ThemeSecuritiesEnvelopeDto(val data: List<MemberSecurityDto>, val meta: MetaDto)

interface IndustryApi {
    @GET("industries")
    suspend fun getIndustries(): IndustryListEnvelopeDto

    @GET("industries/{id}")
    suspend fun getIndustry(@Path("id") id: String): IndustryEnvelopeDto

    @GET("industries/{id}/securities")
    suspend fun getIndustrySecurities(@Path("id") id: String): IndustrySecuritiesEnvelopeDto

    @GET("themes")
    suspend fun getThemes(): ThemeListEnvelopeDto

    @GET("themes/{id}")
    suspend fun getTheme(@Path("id") id: String): ThemeEnvelopeDto

    @GET("themes/{id}/securities")
    suspend fun getThemeSecurities(@Path("id") id: String): ThemeSecuritiesEnvelopeDto
}
