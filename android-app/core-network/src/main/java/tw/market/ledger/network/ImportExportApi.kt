package tw.market.ledger.network

import com.squareup.moshi.Json
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Streaming

data class ImportRowErrorDto(
    val row: Int,
    @Json(name = "error_code") val errorCode: String,
    val message: String,
)

data class PortfolioImportPreviewDto(
    val token: String,
    @Json(name = "portfolio_id") val portfolioId: String?,
    @Json(name = "total_rows") val totalRows: Int,
    @Json(name = "valid_rows") val validRows: Int,
    @Json(name = "invalid_rows") val invalidRows: Int,
    @Json(name = "warning_rows") val warningRows: Int,
    @Json(name = "duplicate_rows") val duplicateRows: Int,
    val errors: List<ImportRowErrorDto>,
    val warnings: List<ImportRowErrorDto>,
)

data class PortfolioImportPreviewEnvelopeDto(val data: PortfolioImportPreviewDto)

data class PortfolioImportApplyInputDto(
    @Json(name = "preview_token") val previewToken: String,
    @Json(name = "portfolio_id") val portfolioId: String,
)

data class ImportApplyResultDto(
    val status: String,
    @Json(name = "inserted_count") val insertedCount: Int,
    @Json(name = "skipped_count") val skippedCount: Int,
    @Json(name = "total_transactions") val totalTransactions: Int,
)

data class ImportApplyResultEnvelopeDto(val data: ImportApplyResultDto)

data class WatchlistImportPreviewDto(
    val token: String,
    @Json(name = "merge_mode") val mergeMode: String,
    @Json(name = "total_rows") val totalRows: Int,
    @Json(name = "valid_rows") val validRows: Int,
    @Json(name = "invalid_rows") val invalidRows: Int,
    val errors: List<ImportRowErrorDto>,
)

data class WatchlistImportPreviewEnvelopeDto(val data: WatchlistImportPreviewDto)

data class WatchlistImportApplyInputDto(
    @Json(name = "preview_token") val previewToken: String,
    @Json(name = "merge_mode") val mergeMode: String,
)

data class WatchlistApplyResultDto(
    val status: String,
    @Json(name = "merge_mode") val mergeMode: String,
    @Json(name = "groups_count") val groupsCount: Int,
    @Json(name = "items_count") val itemsCount: Int,
)

data class WatchlistApplyResultEnvelopeDto(val data: WatchlistApplyResultDto)

data class CsvImportTextInputDto(
    @Json(name = "csv_content") val csvContent: String,
    @Json(name = "portfolio_id") val portfolioId: String? = null,
    @Json(name = "merge_mode") val mergeMode: String = "MERGE",
)

interface ImportExportApi {
    @Streaming
    @GET("exports/portfolio/{portfolio_id}/transactions.csv")
    suspend fun exportPortfolioTransactions(
        @Path("portfolio_id") portfolioId: String,
    ): ResponseBody

    @Streaming
    @GET("exports/portfolio/{portfolio_id}/holdings.csv")
    suspend fun exportPortfolioHoldings(
        @Path("portfolio_id") portfolioId: String,
    ): ResponseBody

    @Streaming
    @GET("exports/portfolio/{portfolio_id}/summary.csv")
    suspend fun exportPortfolioSummary(
        @Path("portfolio_id") portfolioId: String,
    ): ResponseBody

    @Streaming
    @GET("exports/watchlists.csv")
    suspend fun exportWatchlists(): ResponseBody

    @Streaming
    @GET("reports/portfolio/{portfolio_id}.pdf")
    suspend fun generatePortfolioReport(
        @Path("portfolio_id") portfolioId: String,
    ): ResponseBody

    @POST("imports/portfolio/preview")
    suspend fun previewPortfolioImport(
        @Body input: CsvImportTextInputDto,
    ): PortfolioImportPreviewEnvelopeDto

    @POST("imports/portfolio/apply")
    suspend fun applyPortfolioImport(
        @Body input: PortfolioImportApplyInputDto,
    ): ImportApplyResultEnvelopeDto

    @POST("imports/watchlists/preview")
    suspend fun previewWatchlistImport(
        @Body input: CsvImportTextInputDto,
    ): WatchlistImportPreviewEnvelopeDto

    @POST("imports/watchlists/apply")
    suspend fun applyWatchlistImport(
        @Body input: WatchlistImportApplyInputDto,
    ): WatchlistApplyResultEnvelopeDto
}
