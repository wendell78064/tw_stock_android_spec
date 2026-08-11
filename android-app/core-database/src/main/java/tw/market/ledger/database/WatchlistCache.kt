package tw.market.ledger.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Entity(tableName = "watchlist_cache", primaryKeys = ["id"])
data class WatchlistEntity(val id: String, val name: String, val sortOrder: Int)

@Entity(tableName = "watchlist_item_cache", primaryKeys = ["watchlistId", "id"])
data class WatchlistItemEntity(
    val watchlistId: String, val id: String, val securityCode: String, val securityName: String,
    val market: String, val sortOrder: Int, val note: String?, val targetPrice: String?,
    val stopPrice: String?, val addPrice: String?, val close: String?, val change: String?,
    val changePercent: String?, val priceAsOf: String?, val dataStatus: String,
    val foreignNet: Long?, val marginBalanceChange: Long?, val priceAboveMa20: Boolean?,
)

@Dao
interface WatchlistDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertGroups(items: List<WatchlistEntity>)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertItems(items: List<WatchlistItemEntity>)
    @Query("DELETE FROM watchlist_cache") suspend fun clearGroups()
    @Query("DELETE FROM watchlist_item_cache WHERE watchlistId=:id") suspend fun clearItems(id: String)
    @Query("SELECT * FROM watchlist_cache ORDER BY sortOrder,id") suspend fun groups(): List<WatchlistEntity>
    @Query("SELECT * FROM watchlist_item_cache WHERE watchlistId=:id ORDER BY sortOrder,id") suspend fun items(id: String): List<WatchlistItemEntity>
}
