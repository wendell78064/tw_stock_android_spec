package tw.market.ledger.network

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

data class ScreenerFieldMetaDto(
    val field_id: String,
    val label: String,
    val category: String,
    val value_type: String,
    val allowed_operators: List<String>,
    val unit: String? = null,
    val supported_windows: List<Int>? = null
)

data class ScreenerFieldsEnvelopeDto(
    val data: List<ScreenerFieldMetaDto>,
    val meta: MetaDto
)

data class RunScreenerInputDto(
    val expression: Map<String, Any?>,
    val trade_date: String? = null,
    val sort_field: String = "code",
    val sort_direction: String = "ASC",
    val limit: Int = 50,
    val offset: Int = 0
)

data class CreateSavedScreenerInputDto(
    val name: String,
    val description: String? = null,
    val expression: Map<String, Any?>,
    val sort_field: String = "code",
    val sort_direction: String = "ASC"
)

data class UpdateSavedScreenerInputDto(
    val name: String? = null,
    val description: String? = null,
    val expression: Map<String, Any?>? = null,
    val sort_field: String? = null,
    val sort_direction: String? = null
)

data class ScreenerResultSecurityDto(
    val security_id: String,
    val code: String,
    val name: String,
    val market: String,
    val industry_name: String? = null,
    val themes: List<String> = emptyList(),
    val close: String? = null,
    val return_pct: String? = null,
    val matched_conditions: List<String> = emptyList(),
    val extra_metrics: Map<String, String?> = emptyMap(),
    val data_status: String
)

data class SavedScreenerDto(
    val id: String,
    val name: String,
    val description: String? = null,
    val expression: Map<String, Any?>,
    val sort_field: String,
    val sort_direction: String,
    val created_at: String,
    val updated_at: String
)

data class SavedScreenerEnvelopeDto(
    val data: SavedScreenerDto,
    val meta: MetaDto
)

data class SavedScreenerListEnvelopeDto(
    val data: List<SavedScreenerDto>,
    val meta: MetaDto
)

data class ScreenerResultEnvelopeDto(
    val data: List<ScreenerResultSecurityDto>,
    val total_count: Int,
    val trade_date: String,
    val meta: MetaDto
)

interface ScreenerApi {
    @GET("screener/fields")
    suspend fun getScreenerFields(): Response<ScreenerFieldsEnvelopeDto>

    @POST("screener/run")
    suspend fun runScreener(@Body input: RunScreenerInputDto): Response<ScreenerResultEnvelopeDto>

    @GET("screeners")
    suspend fun listSavedScreeners(): Response<SavedScreenerListEnvelopeDto>

    @POST("screeners")
    suspend fun createSavedScreener(@Body input: CreateSavedScreenerInputDto): Response<SavedScreenerEnvelopeDto>

    @GET("screeners/{id}")
    suspend fun getSavedScreener(@Path("id") id: String): Response<SavedScreenerEnvelopeDto>

    @PATCH("screeners/{id}")
    suspend fun updateSavedScreener(@Path("id") id: String, @Body input: UpdateSavedScreenerInputDto): Response<SavedScreenerEnvelopeDto>

    @DELETE("screeners/{id}")
    suspend fun deleteSavedScreener(@Path("id") id: String): Response<Unit>

    @POST("screeners/{id}/run")
    suspend fun runSavedScreener(
        @Path("id") id: String,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): Response<ScreenerResultEnvelopeDto>
}
