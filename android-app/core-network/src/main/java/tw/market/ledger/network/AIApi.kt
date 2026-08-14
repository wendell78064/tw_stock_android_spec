package tw.market.ledger.network

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

@JsonClass(generateAdapter = true)
data class AIAnalyzeRequest(
    val analysis_type: String,
    val target_id: String? = null,
    val comparison_ids: List<String>? = null,
    val screener_expression: Map<String, Any>? = null,
)

@JsonClass(generateAdapter = true)
data class AnalysisStatementDto(
    val type: String,
    val text: String,
    val category: String? = null,
)

@JsonClass(generateAdapter = true)
data class StructuredAIAnalysisResultDto(
    val summary: String,
    val statements: List<AnalysisStatementDto>,
    val risks: List<String>,
    val data_caveats: List<String>,
    val generated_at: String,
    val provider: String,
    val model: String,
    val prompt_version: String,
    val grounding_as_of: String,
    val cache_hit: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class AIConsentResponseDto(
    val allow_portfolio_analysis: Boolean,
)

@JsonClass(generateAdapter = true)
data class SetAIConsentRequestDto(
    val allow_portfolio_analysis: Boolean,
)

interface AIApi {
    @POST("ai/analyze")
    suspend fun analyze(@Body request: AIAnalyzeRequest): StructuredAIAnalysisResultDto

    @GET("ai/consent")
    suspend fun getConsent(): AIConsentResponseDto

    @POST("ai/consent")
    suspend fun setConsent(@Body request: SetAIConsentRequestDto): AIConsentResponseDto
}
