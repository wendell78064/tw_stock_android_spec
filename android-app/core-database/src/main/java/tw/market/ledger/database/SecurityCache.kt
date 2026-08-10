package tw.market.ledger.database

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.RoomDatabase

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

@Database(entities = [SecurityEntity::class], version = 1, exportSchema = false)
abstract class TWMarketDatabase : RoomDatabase() {
    abstract fun securityDao(): SecurityDao
}
