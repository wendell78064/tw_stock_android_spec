package tw.market.ledger.database

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.RoomDatabase
import tw.market.ledger.model.Candle

@Entity(tableName = "security_cache", primaryKeys = ["market", "code"])
data class SecurityEntity(
    val id: String,
    val market: String,
    val code: String,
    val name: String,
    val securityType: String,
    val status: String,
    val primaryIndustry: String?,
    val listingDate: String?,
    val isActive: Boolean,
    val asOf: String,
    val receivedAt: String,
    val dataStatus: String,
)

@Dao
interface SecurityDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(items: List<SecurityEntity>)

    @Query("""
        SELECT * FROM security_cache
        WHERE isActive = 1 AND (:market IS NULL OR market = :market)
          AND (code LIKE :prefix OR name LIKE :contains)
        ORDER BY CASE WHEN code = :query THEN 0 ELSE 1 END, code
        LIMIT :limit
    """)
    suspend fun search(query: String, prefix: String, contains: String, market: String?, limit: Int): List<SecurityEntity>

    @Query("SELECT * FROM security_cache WHERE code = :code AND market = :market LIMIT 1")
    suspend fun detail(code: String, market: String): SecurityEntity?
}

@Entity(
    tableName = "candle_cache",
    primaryKeys = ["market", "code", "range", "interval", "adjustment", "time"],
)
data class CandleEntity(
    val market: String,
    val code: String,
    val range: String,
    val interval: String,
    val adjustment: String,
    val time: String,
    val open: String,
    val high: String,
    val low: String,
    val close: String,
    val volumeShares: Long?,
    val turnoverAmount: String?,
    val asOf: String,
    val dataStatus: String,
)

@Entity(
    tableName = "technical_cache",
    primaryKeys = ["market", "code", "basis", "tradeDate", "name"],
)
data class TechnicalEntity(
    val market: String,
    val code: String,
    val basis: String,
    val tradeDate: String,
    val name: String,
    val value: String?,
    val algorithmVersion: String,
    val asOf: String,
    val dataStatus: String,
)

@Dao
interface ChartDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertCandles(items: List<CandleEntity>)

    @Query("DELETE FROM candle_cache WHERE market=:market AND code=:code AND range=:range AND interval=:interval AND adjustment=:adjustment")
    suspend fun clearCandles(market: String, code: String, range: String, interval: String, adjustment: String)

    @Query("SELECT * FROM candle_cache WHERE market=:market AND code=:code AND range=:range AND interval=:interval AND adjustment=:adjustment ORDER BY time")
    suspend fun candles(market: String, code: String, range: String, interval: String, adjustment: String): List<CandleEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertTechnicals(items: List<TechnicalEntity>)

    @Query("SELECT * FROM technical_cache WHERE market=:market AND code=:code AND basis=:basis ORDER BY tradeDate,name")
    suspend fun technicals(market: String, code: String, basis: String): List<TechnicalEntity>
}

@Entity(tableName = "market_index_cache", primaryKeys = ["code", "tradeDate"])
data class MarketIndexEntity(val code: String, val name: String, val market: String, val tradeDate: String,
    val open: String?, val high: String?, val low: String?, val close: String?, val change: String?,
    val changePercent: String?, val turnoverAmount: String?, val volume: Long?, val asOf: String,
    val dataStatus: String)
@Entity(tableName = "market_breadth_cache", primaryKeys = ["market", "tradeDate"])
data class MarketBreadthEntity(val market: String, val tradeDate: String, val advancers: Int?,
    val decliners: Int?, val unchanged: Int?, val limitUp: Int?, val limitDown: Int?,
    val totalTraded: Int?, val turnoverAmount: String?, val asOf: String, val dataStatus: String)
@Entity(tableName = "institutional_cache", primaryKeys = ["dataset", "market", "security", "window", "tradeDate", "institution", "dealerSubtype"])
data class InstitutionalEntity(val dataset: String, val market: String, val security: String,
    val window: Int, val tradeDate: String, val institution: String, val dealerSubtype: String,
    val buy: String?, val sell: String?, val net: String?, val cumulativeNet: String?,
    val consecutiveDays: Int, val asOf: String, val dataStatus: String)
@Entity(tableName = "credit_cache", primaryKeys = ["dataset", "market", "security", "window", "tradeDate"])
data class CreditEntity(val dataset: String, val market: String, val security: String, val window: Int,
    val tradeDate: String, val balance: Long?, val change: Long?, val secondaryBalance: Long?,
    val secondaryChange: Long?, val ratio: String?, val asOf: String, val dataStatus: String)

@Entity(tableName = "futures_overview_cache", primaryKeys = ["productCode"])
data class FuturesOverviewEntity(val productCode: String, val productName: String,
    val multiplier: String, val currency: String, val contractCode: String?, val contractMonth: String?,
    val tradeDate: String?, val close: String?, val change: String?, val changePercent: String?,
    val volume: Long?, val openInterest: Long?, val closeBasis: String?, val asOf: String?,
    val dataStatus: String)

@Dao interface DerivativesDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(item: FuturesOverviewEntity)
    @Query("SELECT * FROM futures_overview_cache WHERE productCode=:product LIMIT 1")
    suspend fun overview(product: String): FuturesOverviewEntity?
}

@Dao
interface MarketDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertIndexes(items: List<MarketIndexEntity>)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertBreadth(items: List<MarketBreadthEntity>)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertInstitutional(items: List<InstitutionalEntity>)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertCredit(items: List<CreditEntity>)
    @Query("SELECT * FROM market_index_cache WHERE tradeDate=(SELECT MAX(tradeDate) FROM market_index_cache) ORDER BY code") suspend fun latestIndexes(): List<MarketIndexEntity>
    @Query("SELECT * FROM market_breadth_cache WHERE tradeDate=(SELECT MAX(tradeDate) FROM market_breadth_cache) ORDER BY market") suspend fun latestBreadth(): List<MarketBreadthEntity>
    @Query("SELECT * FROM institutional_cache WHERE dataset=:dataset AND market=:market AND security=:security AND window=:window ORDER BY tradeDate,institution,dealerSubtype") suspend fun institutional(dataset: String, market: String, security: String, window: Int): List<InstitutionalEntity>
    @Query("SELECT * FROM credit_cache WHERE dataset=:dataset AND market=:market AND security=:security AND window=:window ORDER BY tradeDate") suspend fun credit(dataset: String, market: String, security: String, window: Int): List<CreditEntity>
}

@Database(
    entities = [SecurityEntity::class, CandleEntity::class, TechnicalEntity::class,
        MarketIndexEntity::class, MarketBreadthEntity::class, InstitutionalEntity::class,
        CreditEntity::class, FuturesOverviewEntity::class, PortfolioSummaryEntity::class,
        PortfolioHoldingEntity::class, PortfolioTransactionEntity::class,
        WatchlistEntity::class, WatchlistItemEntity::class, AlertRuleEntity::class,
        AlertEventEntity::class],
    version = 7,
    exportSchema = false,
)
abstract class TWMarketDatabase : RoomDatabase() {
    abstract fun securityDao(): SecurityDao
    abstract fun chartDao(): ChartDao
    abstract fun marketDao(): MarketDao
    abstract fun derivativesDao(): DerivativesDao
    abstract fun portfolioDao(): PortfolioDao
    abstract fun watchlistDao(): WatchlistDao
    abstract fun alertDao(): AlertDao
}
