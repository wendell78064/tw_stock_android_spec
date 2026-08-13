package tw.market.ledger

import androidx.room.withTransaction
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import java.time.Instant
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import tw.market.ledger.database.CloudSyncDao
import tw.market.ledger.database.CloudWatchlistEntity
import tw.market.ledger.database.CloudWatchlistItemEntity
import tw.market.ledger.database.SyncCursorEntity
import tw.market.ledger.database.SyncOutboxEntity
import tw.market.ledger.database.TWMarketDatabase
import tw.market.ledger.network.SyncApi
import tw.market.ledger.network.SyncOperation
import tw.market.ledger.network.SyncPushRequest

/** Server-authoritative, foreground/manual sync. The Room outbox survives process death. */
@Singleton
class CloudSyncManager @Inject constructor(private val api: SyncApi, private val database: TWMarketDatabase,
    private val dao: CloudSyncDao, private val sessions: KeystoreSessionStore) {
    private val adapter = Moshi.Builder().build().adapter<Map<String, Any?>>(
        Types.newParameterizedType(Map::class.java, String::class.java, Any::class.java))

    suspend fun enqueue(entityType: String, entityId: String, mutation: String,
        baseVersion: Long, payloadJson: String?) {
        val user = requireNotNull(sessions.userId())
        dao.enqueue(SyncOutboxEntity(UUID.randomUUID().toString(), user, entityType, entityId,
            mutation, baseVersion, payloadJson, Instant.now().toString(), 0, null))
    }

    suspend fun sync(): SyncSummary {
        val user = requireNotNull(sessions.userId())
        val pending = dao.pending(user, 100)
        var conflicts = 0
        if (pending.isNotEmpty()) {
            val response = api.push(SyncPushRequest(requireNotNull(sessions.deviceServerId()), pending.map {
                SyncOperation(it.operationId, it.entityType, it.entityId, it.mutation, it.baseVersion,
                    it.payloadJson?.let(adapter::fromJson))
            })).data
            database.withTransaction {
                response.results.forEach { result ->
                    when (result.status) {
                        "ACCEPTED", "DUPLICATE" -> dao.accepted(user, result.operationId)
                        "CONFLICT" -> { conflicts++; dao.failed(user, result.operationId, "CONFLICT") }
                        else -> dao.failed(user, result.operationId, "ERROR")
                    }
                }
            }
        }
        var cursor = dao.cursor(user) ?: 0
        do {
            val page = api.changes(cursor).data
            database.withTransaction {
                page.changes.forEach { change -> apply(user, change.entityType, change.entityId,
                    change.version, change.value, change.operation == "DELETE") }
                cursor = page.nextCursor
                dao.setCursor(SyncCursorEntity(user, cursor))
            }
        } while (page.hasMore)
        return SyncSummary(pending.size, conflicts, cursor)
    }

    private suspend fun apply(user: String, type: String, id: String, version: Long,
        value: Map<String, Any?>?, deleted: Boolean) {
        val json = adapter.toJson(value ?: emptyMap())
        val now = Instant.now().toString()
        if (type == "WATCHLIST") dao.upsertGroups(listOf(CloudWatchlistEntity(id, user, json,
            version, if (deleted) "SYNCED" else "SYNCED", now, if (deleted) now else null)))
        else dao.upsertItems(listOf(CloudWatchlistItemEntity(id, user,
            value?.get("watchlist_id")?.toString().orEmpty(), json, version, "SYNCED", now,
            if (deleted) now else null)))
    }
}

data class SyncSummary(val pushed: Int, val conflicts: Int, val cursor: Long)
