package tw.market.ledger.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Entity(tableName = "cloud_watchlist_cache", indices = [Index("userId")])
data class CloudWatchlistEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val payloadJson: String,
    val serverVersion: Long,
    val syncState: String,
    val updatedAt: String,
    val deletedAt: String?
)

@Entity(tableName = "cloud_watchlist_item_cache", indices = [Index("userId")])
data class CloudWatchlistItemEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val watchlistId: String,
    val payloadJson: String,
    val serverVersion: Long,
    val syncState: String,
    val updatedAt: String,
    val deletedAt: String?
)

@Entity(tableName = "cloud_portfolio_cache", indices = [Index("userId")])
data class CloudPortfolioEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val payloadJson: String,
    val serverVersion: Long,
    val syncState: String,
    val updatedAt: String,
    val deletedAt: String?
)

@Entity(tableName = "cloud_portfolio_transaction_cache", indices = [Index("userId")])
data class CloudPortfolioTransactionEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val portfolioId: String,
    val payloadJson: String,
    val serverVersion: Long,
    val syncState: String,
    val updatedAt: String,
    val deletedAt: String?
)

@Entity(tableName = "cloud_alert_rule_cache", indices = [Index("userId")])
data class CloudAlertRuleEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val payloadJson: String,
    val serverVersion: Long,
    val syncState: String,
    val updatedAt: String,
    val deletedAt: String?
)

@Entity(tableName = "cloud_saved_screener_cache", indices = [Index("userId")])
data class CloudSavedScreenerEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val payloadJson: String,
    val serverVersion: Long,
    val syncState: String,
    val updatedAt: String,
    val deletedAt: String?
)

@Entity(tableName = "cloud_user_setting_cache", indices = [Index("userId")])
data class CloudUserSettingEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val key: String,
    val valueJson: String,
    val serverVersion: Long,
    val syncState: String,
    val updatedAt: String,
    val deletedAt: String?
)

@Entity(tableName = "sync_outbox", indices = [Index("userId")])
data class SyncOutboxEntity(
    @PrimaryKey val operationId: String,
    val userId: String,
    val entityType: String,
    val entityId: String,
    val mutation: String,
    val baseVersion: Long,
    val payloadJson: String?,
    val createdAt: String,
    val attempts: Int,
    val lastError: String?
)

@Entity(tableName = "sync_cursor")
data class SyncCursorEntity(@PrimaryKey val userId: String, val cursor: Long)

@Dao
interface CloudSyncDao {
    @Query("SELECT * FROM sync_outbox WHERE userId=:userId ORDER BY createdAt LIMIT :limit")
    suspend fun pending(userId: String, limit: Int): List<SyncOutboxEntity>

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun enqueue(item: SyncOutboxEntity): Long

    @Query("DELETE FROM sync_outbox WHERE operationId=:operationId AND userId=:userId")
    suspend fun accepted(userId: String, operationId: String)

    @Query("UPDATE sync_outbox SET attempts=attempts+1,lastError=:error WHERE operationId=:operationId AND userId=:userId")
    suspend fun failed(userId: String, operationId: String, error: String)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertGroups(items: List<CloudWatchlistEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertItems(items: List<CloudWatchlistItemEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertPortfolios(items: List<CloudPortfolioEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertPortfolioTransactions(items: List<CloudPortfolioTransactionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAlertRules(items: List<CloudAlertRuleEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertSavedScreeners(items: List<CloudSavedScreenerEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertUserSettings(items: List<CloudUserSettingEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun setCursor(cursor: SyncCursorEntity)

    @Query("SELECT cursor FROM sync_cursor WHERE userId=:userId")
    suspend fun cursor(userId: String): Long?

    @Query("DELETE FROM cloud_watchlist_cache WHERE userId=:userId")
    suspend fun clearGroups(userId: String)

    @Query("DELETE FROM cloud_watchlist_item_cache WHERE userId=:userId")
    suspend fun clearItems(userId: String)

    @Query("DELETE FROM cloud_portfolio_cache WHERE userId=:userId")
    suspend fun clearPortfolios(userId: String)

    @Query("DELETE FROM cloud_portfolio_transaction_cache WHERE userId=:userId")
    suspend fun clearPortfolioTransactions(userId: String)

    @Query("DELETE FROM cloud_alert_rule_cache WHERE userId=:userId")
    suspend fun clearAlertRules(userId: String)

    @Query("DELETE FROM cloud_saved_screener_cache WHERE userId=:userId")
    suspend fun clearSavedScreeners(userId: String)

    @Query("DELETE FROM cloud_user_setting_cache WHERE userId=:userId")
    suspend fun clearUserSettings(userId: String)

    @Query("DELETE FROM sync_outbox WHERE userId=:userId")
    suspend fun clearOutbox(userId: String)

    @Query("DELETE FROM sync_cursor WHERE userId=:userId")
    suspend fun clearCursor(userId: String)
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

val MIGRATION_11_12 = object : Migration(11, 12) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS `cloud_portfolio_cache` (`id` TEXT NOT NULL, `userId` TEXT NOT NULL, `payloadJson` TEXT NOT NULL, `serverVersion` INTEGER NOT NULL, `syncState` TEXT NOT NULL, `updatedAt` TEXT NOT NULL, `deletedAt` TEXT, PRIMARY KEY(`id`))")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_cloud_portfolio_cache_userId` ON `cloud_portfolio_cache` (`userId`)")
        db.execSQL("CREATE TABLE IF NOT EXISTS `cloud_portfolio_transaction_cache` (`id` TEXT NOT NULL, `userId` TEXT NOT NULL, `portfolioId` TEXT NOT NULL, `payloadJson` TEXT NOT NULL, `serverVersion` INTEGER NOT NULL, `syncState` TEXT NOT NULL, `updatedAt` TEXT NOT NULL, `deletedAt` TEXT, PRIMARY KEY(`id`))")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_cloud_portfolio_transaction_cache_userId` ON `cloud_portfolio_transaction_cache` (`userId`)")
        db.execSQL("CREATE TABLE IF NOT EXISTS `cloud_alert_rule_cache` (`id` TEXT NOT NULL, `userId` TEXT NOT NULL, `payloadJson` TEXT NOT NULL, `serverVersion` INTEGER NOT NULL, `syncState` TEXT NOT NULL, `updatedAt` TEXT NOT NULL, `deletedAt` TEXT, PRIMARY KEY(`id`))")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_cloud_alert_rule_cache_userId` ON `cloud_alert_rule_cache` (`userId`)")
        db.execSQL("CREATE TABLE IF NOT EXISTS `cloud_saved_screener_cache` (`id` TEXT NOT NULL, `userId` TEXT NOT NULL, `payloadJson` TEXT NOT NULL, `serverVersion` INTEGER NOT NULL, `syncState` TEXT NOT NULL, `updatedAt` TEXT NOT NULL, `deletedAt` TEXT, PRIMARY KEY(`id`))")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_cloud_saved_screener_cache_userId` ON `cloud_saved_screener_cache` (`userId`)")
        db.execSQL("CREATE TABLE IF NOT EXISTS `cloud_user_setting_cache` (`id` TEXT NOT NULL, `userId` TEXT NOT NULL, `key` TEXT NOT NULL, `valueJson` TEXT NOT NULL, `serverVersion` INTEGER NOT NULL, `syncState` TEXT NOT NULL, `updatedAt` TEXT NOT NULL, `deletedAt` TEXT, PRIMARY KEY(`id`))")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_cloud_user_setting_cache_userId` ON `cloud_user_setting_cache` (`userId`)")
    }
}
