package tw.market.ledger.database

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
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

@Entity(tableName = "saved_screener_cache")
data class SavedScreenerEntity(
    @PrimaryKey val id: String,
    val name: String,
    val description: String?,
    val expressionJson: String,
    val sortField: String,
    val sortDirection: String,
    val updatedAt: String
)

@Entity(tableName = "screener_result_cache")
data class ScreenerResultEntity(
    @PrimaryKey val securityId: String,
    val code: String,
    val name: String,
    val market: String,
    val industryName: String?,
    val themesJson: String,
    val close: String?,
    val returnPct: String?,
    val matchedConditionsJson: String,
    val extraMetricsJson: String,
    val dataStatus: String,
    val cachedAt: String
)

@Dao
interface ScreenerDao {
    @Query("SELECT * FROM saved_screener_cache ORDER BY updatedAt DESC")
    suspend fun getSavedScreeners(): List<SavedScreenerEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertSavedScreeners(screeners: List<SavedScreenerEntity>)

    @Query("DELETE FROM saved_screener_cache WHERE id = :id")
    suspend fun deleteSavedScreener(id: String)

    @Query("SELECT * FROM screener_result_cache ORDER BY code ASC")
    suspend fun getCachedScreenerResults(): List<ScreenerResultEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun replaceCachedScreenerResults(results: List<ScreenerResultEntity>)

    @Query("DELETE FROM screener_result_cache")
    suspend fun clearScreenerResults()
}

val MIGRATION_9_10 = object : Migration(9, 10) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE IF NOT EXISTS saved_screener_cache (
                id TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                expressionJson TEXT NOT NULL,
                sortField TEXT NOT NULL,
                sortDirection TEXT NOT NULL,
                updatedAt TEXT NOT NULL
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE TABLE IF NOT EXISTS screener_result_cache (
                securityId TEXT NOT NULL PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                market TEXT NOT NULL,
                industryName TEXT,
                themesJson TEXT NOT NULL,
                close TEXT,
                returnPct TEXT,
                matchedConditionsJson TEXT NOT NULL,
                extraMetricsJson TEXT NOT NULL,
                dataStatus TEXT NOT NULL,
                cachedAt TEXT NOT NULL
            )
            """.trimIndent()
        )
    }
}

@Database(
    entities = [SecurityEntity::class, CandleEntity::class, TechnicalEntity::class,
        MarketIndexEntity::class, MarketBreadthEntity::class, InstitutionalEntity::class,
        CreditEntity::class, FuturesOverviewEntity::class, PortfolioSummaryEntity::class,
        PortfolioHoldingEntity::class, PortfolioTransactionEntity::class,
        WatchlistEntity::class, WatchlistItemEntity::class, AlertRuleEntity::class,
        AlertEventEntity::class, IndustryEntity::class, ThemeEntity::class, TaxonomyMemberEntity::class,
        TaxonomyStrengthEntity::class, TaxonomyLeaderEntity::class,
        SavedScreenerEntity::class, ScreenerResultEntity::class, CloudWatchlistEntity::class,
        CloudWatchlistItemEntity::class, CloudPortfolioEntity::class, CloudPortfolioTransactionEntity::class,
        CloudAlertRuleEntity::class, CloudSavedScreenerEntity::class, CloudUserSettingEntity::class,
        SyncOutboxEntity::class, SyncCursorEntity::class],
    version = 12,
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
    abstract fun taxonomyDao(): TaxonomyDao
    abstract fun screenerDao(): ScreenerDao
    abstract fun cloudSyncDao(): CloudSyncDao
}
