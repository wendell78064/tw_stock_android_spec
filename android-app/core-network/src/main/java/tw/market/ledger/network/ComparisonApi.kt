package tw.market.ledger.network

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST

data class SecurityTargetInputDto(
    val code: String,
    val market: String
)

data class RunComparisonInputDto(
    val targets: List<SecurityTargetInputDto>,
    val window: String = "20D",
    val trade_date: String? = null
)

data class NormalizedPointDto(
    val trade_date: String,
    val values: Map<String, String?>
)

data class ObjectiveSignalDto(
    val signal_type: String,
    val subject_code: String,
    val comparator_code: String,
    val headline: String,
    val details: String,
    val metrics: Map<String, Any> = emptyMap()
)

data class ComparisonSecuritySummaryDto(
    val security_id: String,
    val code: String,
    val name: String,
    val market: String,
    val latest_close: String? = null,
    val return_1d: String? = null,
    val return_5d: String? = null,
    val return_10d: String? = null,
    val return_20d: String? = null,
    val return_60d: String? = null,
    val return_selected_window: String? = null,
    val ma5: String? = null,
    val ma20: String? = null,
    val ma60: String? = null,
    val close_vs_ma20: String? = null,
    val close_vs_ma60: String? = null,
    val rsi14: String? = null,
    val macd_state: String? = null,
    val kd_state: String? = null,
    val foreign_1d_net: String? = null,
    val foreign_5d_net: String? = null,
    val trust_1d_net: String? = null,
    val trust_5d_net: String? = null,
    val dealer_1d_net: String? = null,
    val dealer_5d_net: String? = null,
    val margin_balance_change: String? = null,
    val short_balance_change: String? = null,
    val lending_balance_change: String? = null,
    val industry_name: String? = null,
    val themes: List<String> = emptyList(),
    val industry_strength_score: String? = null,
    val industry_strength_rank: Int? = null,
    val selected_set_return_rank: Int? = null,
    val selected_set_rsi_rank: Int? = null,
    val selected_set_foreign_rank: Int? = null,
    val data_status: String
)

data class ComparisonResultDto(
    val window: String,
    val requested_start: String,
    val effective_start: String,
    val effective_end: String,
    val securities: List<ComparisonSecuritySummaryDto>,
    val normalized_series: List<NormalizedPointDto>,
    val objective_signals: List<ObjectiveSignalDto>,
    val coverage: String
)

data class ComparisonEnvelopeDto(
    val data: ComparisonResultDto,
    val meta: MetaDto
)

data class ComparisonAnalysisPromptInputDto(
    val securities: List<SecurityTargetInputDto>
)

data class ComparisonAnalysisPromptDto(
    val securities: List<SecurityDto>,
    @com.squareup.moshi.Json(name = "generated_at") val generatedAt: String,
    val prompt: String,
    @com.squareup.moshi.Json(name = "character_count") val characterCount: Int,
    @com.squareup.moshi.Json(name = "data_status") val dataStatus: String,
)

data class ComparisonAnalysisPromptEnvelopeDto(
    val data: ComparisonAnalysisPromptDto,
    val meta: MetaDto,
)

interface ComparisonApi {
    @POST("comparisons/run")
    suspend fun runComparison(@Body input: RunComparisonInputDto): Response<ComparisonEnvelopeDto>

    @POST("comparisons/analysis-prompt")
    suspend fun getComparisonAnalysisPrompt(
        @Body input: ComparisonAnalysisPromptInputDto
    ): Response<ComparisonAnalysisPromptEnvelopeDto>
}

