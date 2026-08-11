package tw.market.ledger.network

import com.squareup.moshi.Json
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

data class PortfolioDto(
    val id: String,
    val name: String,
    @Json(name = "base_currency") val baseCurrency: String,
    @Json(name = "is_default") val isDefault: Boolean,
)
data class PortfolioEnvelopeDto(val data: PortfolioDto)
data class PortfolioListEnvelopeDto(val data: List<PortfolioDto>)

data class PortfolioSummaryDto(
    @Json(name = "total_market_value") val totalMarketValue: String?,
    @Json(name = "total_cost_basis") val totalCostBasis: String,
    @Json(name = "total_unrealized_pnl") val totalUnrealizedPnl: String?,
    @Json(name = "total_realized_pnl") val totalRealizedPnl: String,
    @Json(name = "total_return_percent") val totalReturnPercent: String?,
    @Json(name = "holding_count") val holdingCount: Int,
    @Json(name = "price_as_of") val priceAsOf: String?,
    @Json(name = "data_status") val dataStatus: String,
    @Json(name = "tax_handling") val taxHandling: String,
)
data class PortfolioSummaryEnvelopeDto(val data: PortfolioSummaryDto)

data class PortfolioHoldingDto(
    @Json(name = "security_code") val securityCode: String,
    @Json(name = "security_name") val securityName: String,
    val market: String,
    @Json(name = "quantity_shares") val quantityShares: Long,
    @Json(name = "average_cost") val averageCost: String?,
    @Json(name = "cost_basis") val costBasis: String,
    @Json(name = "realized_pnl") val realizedPnl: String,
    @Json(name = "latest_price") val latestPrice: String?,
    @Json(name = "price_as_of") val priceAsOf: String?,
    @Json(name = "price_data_status") val priceDataStatus: String,
    @Json(name = "market_value") val marketValue: String?,
    @Json(name = "unrealized_pnl") val unrealizedPnl: String?,
    @Json(name = "unrealized_return_percent") val unrealizedReturnPercent: String?,
    @Json(name = "allocation_percent") val allocationPercent: String?,
)
data class PortfolioHoldingListEnvelopeDto(val data: List<PortfolioHoldingDto>)

data class PortfolioTransactionDto(
    val id: String,
    @Json(name = "portfolio_id") val portfolioId: String,
    @Json(name = "security_code") val securityCode: String,
    @Json(name = "security_name") val securityName: String,
    val market: String,
    val side: String,
    @Json(name = "executed_at") val executedAt: String,
    @Json(name = "quantity_shares") val quantityShares: Long,
    val price: String,
    val fee: String,
    @Json(name = "lot_type") val lotType: String,
)
data class PortfolioTransactionEnvelopeDto(val data: PortfolioTransactionDto)
data class PortfolioTransactionListEnvelopeDto(val data: List<PortfolioTransactionDto>)
data class TransactionInputDto(
    @Json(name = "security_code") val securityCode: String,
    val market: String?,
    val side: String,
    @Json(name = "executed_at") val executedAt: String,
    @Json(name = "quantity_shares") val quantityShares: Long,
    val price: String,
    val fee: String,
    @Json(name = "lot_type") val lotType: String,
)

interface PortfolioApi {
    @GET("portfolios") suspend fun portfolios(): PortfolioListEnvelopeDto
    @GET("portfolios/{id}/summary") suspend fun summary(@Path("id") id: String): PortfolioSummaryEnvelopeDto
    @GET("portfolios/{id}/positions") suspend fun positions(@Path("id") id: String): PortfolioHoldingListEnvelopeDto
    @GET("portfolios/{id}/transactions") suspend fun transactions(@Path("id") id: String): PortfolioTransactionListEnvelopeDto
    @POST("portfolios/{id}/transactions") suspend fun addTransaction(
        @Path("id") id: String,
        @Body input: TransactionInputDto,
    ): PortfolioTransactionEnvelopeDto
    @DELETE("portfolios/{id}/transactions/{transactionId}") suspend fun deleteTransaction(
        @Path("id") id: String,
        @Path("transactionId") transactionId: String,
    )
}
