package tw.market.ledger.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Entity(tableName = "portfolio_summary_cache", primaryKeys = ["portfolioId"])
data class PortfolioSummaryEntity(
    val portfolioId: String,
    val totalMarketValue: String?,
    val totalCostBasis: String,
    val totalUnrealizedPnl: String?,
    val totalRealizedPnl: String,
    val totalReturnPercent: String?,
    val holdingCount: Int,
    val priceAsOf: String?,
    val dataStatus: String,
    val taxHandling: String,
)

@Entity(tableName = "portfolio_holding_cache", primaryKeys = ["portfolioId", "market", "securityCode"])
data class PortfolioHoldingEntity(
    val portfolioId: String,
    val securityCode: String,
    val securityName: String,
    val market: String,
    val quantityShares: Long,
    val averageCost: String?,
    val costBasis: String,
    val realizedPnl: String,
    val latestPrice: String?,
    val priceAsOf: String?,
    val priceDataStatus: String,
    val marketValue: String?,
    val unrealizedPnl: String?,
    val unrealizedReturnPercent: String?,
    val allocationPercent: String?,
)

@Entity(tableName = "portfolio_transaction_cache", primaryKeys = ["portfolioId", "id"])
data class PortfolioTransactionEntity(
    val portfolioId: String,
    val id: String,
    val securityCode: String,
    val securityName: String,
    val market: String,
    val side: String,
    val executedAt: String,
    val quantityShares: Long,
    val price: String,
    val fee: String,
    val lotType: String,
)

@Dao
interface PortfolioDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertSummary(item: PortfolioSummaryEntity)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertHoldings(items: List<PortfolioHoldingEntity>)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertTransactions(items: List<PortfolioTransactionEntity>)
    @Query("DELETE FROM portfolio_holding_cache WHERE portfolioId=:portfolioId") suspend fun clearHoldings(portfolioId: String)
    @Query("DELETE FROM portfolio_transaction_cache WHERE portfolioId=:portfolioId") suspend fun clearTransactions(portfolioId: String)
    @Query("SELECT * FROM portfolio_summary_cache WHERE portfolioId=:portfolioId") suspend fun summary(portfolioId: String): PortfolioSummaryEntity?
    @Query("SELECT * FROM portfolio_summary_cache LIMIT 1") suspend fun firstSummary(): PortfolioSummaryEntity?
    @Query("SELECT * FROM portfolio_holding_cache WHERE portfolioId=:portfolioId") suspend fun holdings(portfolioId: String): List<PortfolioHoldingEntity>
    @Query("SELECT * FROM portfolio_transaction_cache WHERE portfolioId=:portfolioId ORDER BY executedAt,id") suspend fun transactions(portfolioId: String): List<PortfolioTransactionEntity>
}
