package tw.market.ledger.network

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import tw.market.ledger.database.CloudAlertRuleEntity
import tw.market.ledger.database.CloudPortfolioEntity
import tw.market.ledger.database.CloudPortfolioTransactionEntity
import tw.market.ledger.database.CloudSavedScreenerEntity
import tw.market.ledger.database.CloudSyncDao
import tw.market.ledger.database.CloudUserSettingEntity
import tw.market.ledger.database.CloudWatchlistEntity
import tw.market.ledger.database.CloudWatchlistItemEntity
import tw.market.ledger.database.SyncCursorEntity
import tw.market.ledger.database.SyncOutboxEntity
import javax.inject.Inject
import javax.inject.Singleton

enum class SyncState {
    SYNCED, PENDING, CONFLICT, ERROR
}

object SyncEntityTypes {
    const val WATCHLIST = "WATCHLIST"
    const val WATCHLIST_ITEM = "WATCHLIST_ITEM"
    const val PORTFOLIO = "PORTFOLIO"
    const val PORTFOLIO_TRANSACTION = "PORTFOLIO_TRANSACTION"
    const val ALERT_RULE = "ALERT_RULE"
    const val SAVED_SCREENER = "SAVED_SCREENER"
    const val USER_SETTING = "USER_SETTING"
}

@Singleton
class CloudSyncManager @Inject constructor(
    private val syncApi: SyncApi,
    private val syncDao: CloudSyncDao,
    private val sessionStore: TokenSessionStore
) {
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    suspend fun enqueue(
        entityType: String,
        entityId: String,
        mutation: String,
        baseVersion: Long,
        payload: Map<String, Any?>?
    ) {
        val userId = sessionStore.userId() ?: return
        val opId = java.util.UUID.randomUUID().toString()
        val payloadJson = payload?.let { moshi.adapter(Map::class.java).toJson(it) }
        syncDao.enqueue(
            SyncOutboxEntity(
                operationId = opId,
                userId = userId,
                entityType = entityType,
                entityId = entityId,
                mutation = mutation,
                baseVersion = baseVersion,
                payloadJson = payloadJson,
                createdAt = java.time.Instant.now().toString(),
                attempts = 0,
                lastError = null
            )
        )
    }

    suspend fun pushPending(deviceId: String): List<SyncResult> {
        val userId = sessionStore.userId() ?: return emptyList()
        val pending = syncDao.pending(userId, 100)
        if (pending.isEmpty()) return emptyList()

        val ops = pending.map { p ->
            val payloadMap = p.payloadJson?.let {
                @Suppress("UNCHECKED_CAST")
                moshi.adapter(Map::class.java).fromJson(it) as? Map<String, Any?>
            }
            SyncOperation(
                operationId = p.operationId,
                entityType = p.entityType,
                entityId = p.entityId,
                operation = p.mutation,
                baseVersion = p.baseVersion,
                payload = payloadMap
            )
        }

        return try {
            val resp = syncApi.push(SyncPushRequest(deviceId = deviceId, operations = ops))
            val results = resp.data.results
            for (r in results) {
                if (r.status == "ACCEPTED" || r.status == "DUPLICATE") {
                    syncDao.accepted(userId, r.operationId)
                } else if (r.status == "CONFLICT" || r.status == "REJECTED") {
                    syncDao.failed(userId, r.operationId, r.status)
                }
            }
            results
        } catch (e: Exception) {
            for (p in pending) {
                syncDao.failed(userId, p.operationId, e.message ?: "Network error")
            }
            emptyList()
        }
    }

    suspend fun syncBootstrap() {
        val userId = sessionStore.userId() ?: return
        try {
            val resp = syncApi.bootstrap().data
            val now = java.time.Instant.now().toString()

            val wls = resp.watchlists.map { item ->
                CloudWatchlistEntity(
                    id = item["id"].toString(),
                    userId = userId,
                    payloadJson = moshi.adapter(Map::class.java).toJson(item),
                    serverVersion = (item["version"] as? Number)?.toLong() ?: 1L,
                    syncState = SyncState.SYNCED.name,
                    updatedAt = item["updated_at"]?.toString() ?: now,
                    deletedAt = item["deleted_at"]?.toString()
                )
            }
            val items = resp.items.map { item ->
                CloudWatchlistItemEntity(
                    id = item["id"].toString(),
                    userId = userId,
                    watchlistId = item["watchlist_id"]?.toString() ?: "",
                    payloadJson = moshi.adapter(Map::class.java).toJson(item),
                    serverVersion = (item["version"] as? Number)?.toLong() ?: 1L,
                    syncState = SyncState.SYNCED.name,
                    updatedAt = item["updated_at"]?.toString() ?: now,
                    deletedAt = item["deleted_at"]?.toString()
                )
            }
            val pfs = resp.portfolios.map { item ->
                CloudPortfolioEntity(
                    id = item["id"].toString(),
                    userId = userId,
                    payloadJson = moshi.adapter(Map::class.java).toJson(item),
                    serverVersion = (item["version"] as? Number)?.toLong() ?: 1L,
                    syncState = SyncState.SYNCED.name,
                    updatedAt = item["updated_at"]?.toString() ?: now,
                    deletedAt = item["deleted_at"]?.toString()
                )
            }
            val txs = resp.portfolioTransactions.map { item ->
                CloudPortfolioTransactionEntity(
                    id = item["id"].toString(),
                    userId = userId,
                    portfolioId = item["portfolio_id"]?.toString() ?: "",
                    payloadJson = moshi.adapter(Map::class.java).toJson(item),
                    serverVersion = (item["version"] as? Number)?.toLong() ?: 1L,
                    syncState = SyncState.SYNCED.name,
                    updatedAt = item["updated_at"]?.toString() ?: now,
                    deletedAt = item["deleted_at"]?.toString()
                )
            }
            val alerts = resp.alertRules.map { item ->
                CloudAlertRuleEntity(
                    id = item["id"].toString(),
                    userId = userId,
                    payloadJson = moshi.adapter(Map::class.java).toJson(item),
                    serverVersion = (item["version"] as? Number)?.toLong() ?: 1L,
                    syncState = SyncState.SYNCED.name,
                    updatedAt = item["updated_at"]?.toString() ?: now,
                    deletedAt = item["deleted_at"]?.toString()
                )
            }
            val screeners = resp.savedScreeners.map { item ->
                CloudSavedScreenerEntity(
                    id = item["id"].toString(),
                    userId = userId,
                    payloadJson = moshi.adapter(Map::class.java).toJson(item),
                    serverVersion = (item["version"] as? Number)?.toLong() ?: 1L,
                    syncState = SyncState.SYNCED.name,
                    updatedAt = item["updated_at"]?.toString() ?: now,
                    deletedAt = item["deleted_at"]?.toString()
                )
            }
            val settings = resp.userSettings.map { item ->
                CloudUserSettingEntity(
                    id = item["id"].toString(),
                    userId = userId,
                    key = item["key"]?.toString() ?: "",
                    valueJson = moshi.adapter(Any::class.java).toJson(item["value"]),
                    serverVersion = (item["version"] as? Number)?.toLong() ?: 1L,
                    syncState = SyncState.SYNCED.name,
                    updatedAt = item["updated_at"]?.toString() ?: now,
                    deletedAt = item["deleted_at"]?.toString()
                )
            }

            syncDao.upsertGroups(wls)
            syncDao.upsertItems(items)
            syncDao.upsertPortfolios(pfs)
            syncDao.upsertPortfolioTransactions(txs)
            syncDao.upsertAlertRules(alerts)
            syncDao.upsertSavedScreeners(screeners)
            syncDao.upsertUserSettings(settings)
            syncDao.setCursor(SyncCursorEntity(userId = userId, cursor = resp.cursor))
        } catch (_: Exception) {
            // Fail safe on bootstrap network issue
        }
    }

    suspend fun clearAllUserData(userId: String) {
        syncDao.clearGroups(userId)
        syncDao.clearItems(userId)
        syncDao.clearPortfolios(userId)
        syncDao.clearPortfolioTransactions(userId)
        syncDao.clearAlertRules(userId)
        syncDao.clearSavedScreeners(userId)
        syncDao.clearUserSettings(userId)
        syncDao.clearOutbox(userId)
        syncDao.clearCursor(userId)
    }
}
