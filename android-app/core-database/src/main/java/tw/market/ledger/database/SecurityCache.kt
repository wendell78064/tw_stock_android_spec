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

@Database(
    entities = [SecurityEntity::class, CandleEntity::class, TechnicalEntity::class],
    version = 2,
    exportSchema = false,
)
abstract class TWMarketDatabase : RoomDatabase() {
    abstract fun securityDao(): SecurityDao
    abstract fun chartDao(): ChartDao
}
