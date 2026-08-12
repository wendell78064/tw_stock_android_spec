package tw.market.ledger.network

import com.squareup.moshi.Json
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

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

data class StrengthComponentsDto(
    @Json(name = "momentum_score") val momentumScore: String? = null,
    @Json(name = "breadth_score") val breadthScore: String? = null,
    @Json(name = "technical_score") val technicalScore: String? = null,
    @Json(name = "institutional_score") val institutionalScore: String? = null,
    @Json(name = "turnover_score") val turnoverScore: String? = null,
)

data class TaxonomyStrengthDto(
    val id: String,
    @Json(name = "taxonomy_id") val taxonomyId: String,
    @Json(name = "taxonomy_code") val taxonomyCode: String,
    @Json(name = "taxonomy_name") val taxonomyName: String,
    @Json(name = "taxonomy_type") val taxonomyType: String,
    @Json(name = "trade_date") val tradeDate: String,
    val window: Int,
    @Json(name = "equal_weight_return") val equalWeightReturn: String,
    @Json(name = "market_cap_weighted_return") val marketCapWeightedReturn: String? = null,
    @Json(name = "total_members") val totalMembers: Int,
    @Json(name = "valid_members") val validMembers: Int,
    @Json(name = "coverage_ratio") val coverageRatio: String,
    val advancers: Int,
    val decliners: Int,
    val unchanged: Int,
    @Json(name = "advance_ratio") val advanceRatio: String,
    @Json(name = "above_ma20_pct") val aboveMa20Pct: String,
    @Json(name = "above_ma60_pct") val aboveMa60Pct: String,
    @Json(name = "foreign_net_amount") val foreignNetAmount: String,
    @Json(name = "investment_trust_net_amount") val investmentTrustNetAmount: String,
    @Json(name = "dealer_net_amount") val dealerNetAmount: String,
    @Json(name = "margin_balance_change") val marginBalanceChange: String,
    @Json(name = "short_balance_change") val shortBalanceChange: String,
    @Json(name = "lending_balance_change") val lendingBalanceChange: String? = null,
    @Json(name = "turnover_amount") val turnoverAmount: String? = null,
    @Json(name = "turnover_share") val turnoverShare: String? = null,
    @Json(name = "turnover_momentum") val turnoverMomentum: String? = null,
    val components: StrengthComponentsDto,
    @Json(name = "strength_score") val strengthScore: String? = null,
    @Json(name = "component_coverage") val componentCoverage: String,
    val rank: Int? = null,
    @Json(name = "algorithm_version") val algorithmVersion: String,
    @Json(name = "data_status") val dataStatus: String,
    @Json(name = "as_of") val asOf: String,
)

data class TaxonomyLeaderDto(
    @Json(name = "security_id") val securityId: String,
    val code: String,
    val name: String,
    val market: String,
    @Json(name = "return_pct") val returnPct: String,
    @Json(name = "latest_close") val latestClose: String? = null,
    @Json(name = "foreign_net") val foreignNet: String? = null,
    @Json(name = "data_status") val dataStatus: String,
)

data class TaxonomyStrengthDetailDto(
    val snapshot: TaxonomyStrengthDto,
    val leaders: List<TaxonomyLeaderDto>,
    val laggards: List<TaxonomyLeaderDto>,
)

data class IndustryListEnvelopeDto(val data: List<IndustryDto>, val meta: MetaDto)
data class IndustryEnvelopeDto(val data: IndustryDto, val meta: MetaDto)
data class IndustrySecuritiesEnvelopeDto(val data: List<MemberSecurityDto>, val meta: MetaDto)

data class ThemeListEnvelopeDto(val data: List<ThemeDto>, val meta: MetaDto)
data class ThemeEnvelopeDto(val data: ThemeDto, val meta: MetaDto)
data class ThemeSecuritiesEnvelopeDto(val data: List<MemberSecurityDto>, val meta: MetaDto)

data class TaxonomyStrengthListEnvelopeDto(val data: List<TaxonomyStrengthDto>, val meta: MetaDto)
data class TaxonomyStrengthDetailEnvelopeDto(val data: TaxonomyStrengthDetailDto, val meta: MetaDto)

interface IndustryApi {
    @GET("industries")
    suspend fun getIndustries(): IndustryListEnvelopeDto

    @GET("industries/{id}")
    suspend fun getIndustry(@Path("id") id: String): IndustryEnvelopeDto

    @GET("industries/{id}/securities")
    suspend fun getIndustrySecurities(@Path("id") id: String): IndustrySecuritiesEnvelopeDto

    @GET("industries/strength")
    suspend fun getIndustryStrengths(
        @Query("window") window: Int = 20,
        @Query("trade_date") tradeDate: String? = null,
        @Query("sort") sort: String = "strength",
    ): TaxonomyStrengthListEnvelopeDto

    @GET("industries/{id}/strength")
    suspend fun getIndustryStrengthDetail(
        @Path("id") id: String,
        @Query("window") window: Int = 20,
        @Query("trade_date") tradeDate: String? = null,
    ): TaxonomyStrengthDetailEnvelopeDto

    @GET("industries/{id}/strength/history")
    suspend fun getIndustryStrengthHistory(
        @Path("id") id: String,
        @Query("window") window: Int = 20,
        @Query("limit") limit: Int = 60,
    ): TaxonomyStrengthListEnvelopeDto

    @GET("themes")
    suspend fun getThemes(): ThemeListEnvelopeDto

    @GET("themes/{id}")
    suspend fun getTheme(@Path("id") id: String): ThemeEnvelopeDto

    @GET("themes/{id}/securities")
    suspend fun getThemeSecurities(@Path("id") id: String): ThemeSecuritiesEnvelopeDto

    @GET("themes/strength")
    suspend fun getThemeStrengths(
        @Query("window") window: Int = 20,
        @Query("trade_date") tradeDate: String? = null,
        @Query("sort") sort: String = "strength",
    ): TaxonomyStrengthListEnvelopeDto

    @GET("themes/{id}/strength")
    suspend fun getThemeStrengthDetail(
        @Path("id") id: String,
        @Query("window") window: Int = 20,
        @Query("trade_date") tradeDate: String? = null,
    ): TaxonomyStrengthDetailEnvelopeDto

    @GET("themes/{id}/strength/history")
    suspend fun getThemeStrengthHistory(
        @Path("id") id: String,
        @Query("window") window: Int = 20,
        @Query("limit") limit: Int = 60,
    ): TaxonomyStrengthListEnvelopeDto
}
