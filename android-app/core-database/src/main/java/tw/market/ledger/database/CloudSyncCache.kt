package tw.market.ledger.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.Index
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Entity(tableName = "cloud_watchlist_cache", indices = [Index("userId")])
data class CloudWatchlistEntity(@PrimaryKey val id: String, val userId: String, val payloadJson: String,
    val serverVersion: Long, val syncState: String, val updatedAt: String, val deletedAt: String?)

@Entity(tableName = "cloud_watchlist_item_cache", indices = [Index("userId")])
data class CloudWatchlistItemEntity(@PrimaryKey val id: String, val userId: String, val watchlistId: String,
    val payloadJson: String, val serverVersion: Long, val syncState: String, val updatedAt: String,
    val deletedAt: String?)

@Entity(tableName = "sync_outbox", indices = [Index("userId")])
data class SyncOutboxEntity(@PrimaryKey val operationId: String, val userId: String,
    val entityType: String, val entityId: String, val mutation: String, val baseVersion: Long,
    val payloadJson: String?, val createdAt: String, val attempts: Int, val lastError: String?)

@Entity(tableName = "sync_cursor")
data class SyncCursorEntity(@PrimaryKey val userId: String, val cursor: Long)

@Dao
interface CloudSyncDao {
    @Query("SELECT * FROM sync_outbox WHERE userId=:userId ORDER BY createdAt LIMIT :limit")
    suspend fun pending(userId: String, limit: Int): List<SyncOutboxEntity>
    @Insert(onConflict = OnConflictStrategy.IGNORE) suspend fun enqueue(item: SyncOutboxEntity): Long
    @Query("DELETE FROM sync_outbox WHERE operationId=:operationId AND userId=:userId")
    suspend fun accepted(userId: String, operationId: String)
    @Query("UPDATE sync_outbox SET attempts=attempts+1,lastError=:error WHERE operationId=:operationId AND userId=:userId")
    suspend fun failed(userId: String, operationId: String, error: String)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertGroups(items: List<CloudWatchlistEntity>)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertItems(items: List<CloudWatchlistItemEntity>)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun setCursor(cursor: SyncCursorEntity)
    @Query("SELECT cursor FROM sync_cursor WHERE userId=:userId") suspend fun cursor(userId: String): Long?
    @Query("DELETE FROM cloud_watchlist_cache WHERE userId=:userId") suspend fun clearGroups(userId: String)
    @Query("DELETE FROM cloud_watchlist_item_cache WHERE userId=:userId") suspend fun clearItems(userId: String)
    @Query("DELETE FROM sync_outbox WHERE userId=:userId") suspend fun clearOutbox(userId: String)
    @Query("DELETE FROM sync_cursor WHERE userId=:userId") suspend fun clearCursor(userId: String)
}

val MIGRATION_10_11 = object : Migration(10, 11) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS `cloud_watchlist_cache` (`id` TEXT NOT NULL, `userId` TEXT NOT NULL, `payloadJson` TEXT NOT NULL, `serverVersion` INTEGER NOT NULL, `syncState` TEXT NOT NULL, `updatedAt` TEXT NOT NULL, `deletedAt` TEXT, PRIMARY KEY(`id`))")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_cloud_watchlist_cache_userId` ON `cloud_watchlist_cache` (`userId`)")
        db.execSQL("CREATE TABLE IF NOT EXISTS `cloud_watchlist_item_cache` (`id` TEXT NOT NULL, `userId` TEXT NOT NULL, `watchlistId` TEXT NOT NULL, `payloadJson` TEXT NOT NULL, `serverVersion` INTEGER NOT NULL, `syncState` TEXT NOT NULL, `updatedAt` TEXT NOT NULL, `deletedAt` TEXT, PRIMARY KEY(`id`))")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_cloud_watchlist_item_cache_userId` ON `cloud_watchlist_item_cache` (`userId`)")
        db.execSQL("CREATE TABLE IF NOT EXISTS `sync_outbox` (`operationId` TEXT NOT NULL, `userId` TEXT NOT NULL, `entityType` TEXT NOT NULL, `entityId` TEXT NOT NULL, `mutation` TEXT NOT NULL, `baseVersion` INTEGER NOT NULL, `payloadJson` TEXT, `createdAt` TEXT NOT NULL, `attempts` INTEGER NOT NULL, `lastError` TEXT, PRIMARY KEY(`operationId`))")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_sync_outbox_userId` ON `sync_outbox` (`userId`)")
        db.execSQL("CREATE TABLE IF NOT EXISTS `sync_cursor` (`userId` TEXT NOT NULL, `cursor` INTEGER NOT NULL, PRIMARY KEY(`userId`))")
    }
}
