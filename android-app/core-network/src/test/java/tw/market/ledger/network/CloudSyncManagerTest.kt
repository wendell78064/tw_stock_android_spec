package tw.market.ledger.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
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

class CloudSyncManagerTest {

    class FakeSyncDao : CloudSyncDao {
        val outbox = mutableListOf<SyncOutboxEntity>()
        val cleared = mutableSetOf<String>()
        val portfolios = mutableListOf<CloudPortfolioEntity>()
        val transactions = mutableListOf<CloudPortfolioTransactionEntity>()

        override suspend fun pending(userId: String, limit: Int): List<SyncOutboxEntity> =
            outbox.filter { it.userId == userId }.take(limit)

        override suspend fun enqueue(item: SyncOutboxEntity): Long {
            outbox.add(item)
            return 1L
        }

        override suspend fun accepted(userId: String, operationId: String) {
            outbox.removeAll { it.userId == userId && it.operationId == operationId }
        }

        override suspend fun failed(userId: String, operationId: String, error: String) {
            val idx = outbox.indexOfFirst { it.userId == userId && it.operationId == operationId }
            if (idx != -1) {
                val old = outbox[idx]
                outbox[idx] = old.copy(attempts = old.attempts + 1, lastError = error)
            }
        }

        override suspend fun upsertGroups(items: List<CloudWatchlistEntity>) {}
        override suspend fun upsertItems(items: List<CloudWatchlistItemEntity>) {}
        override suspend fun upsertPortfolios(items: List<CloudPortfolioEntity>) { portfolios.addAll(items) }
        override suspend fun upsertPortfolioTransactions(items: List<CloudPortfolioTransactionEntity>) { transactions.addAll(items) }
        override suspend fun upsertAlertRules(items: List<CloudAlertRuleEntity>) {}
        override suspend fun upsertSavedScreeners(items: List<CloudSavedScreenerEntity>) {}
        override suspend fun upsertUserSettings(items: List<CloudUserSettingEntity>) {}
        override suspend fun setCursor(cursor: SyncCursorEntity) {}
        override suspend fun cursor(userId: String): Long? = 10L

        override suspend fun clearGroups(userId: String) { cleared.add("groups_$userId") }
        override suspend fun clearItems(userId: String) { cleared.add("items_$userId") }
        override suspend fun clearPortfolios(userId: String) { cleared.add("portfolios_$userId") }
        override suspend fun clearPortfolioTransactions(userId: String) { cleared.add("transactions_$userId") }
        override suspend fun clearAlertRules(userId: String) { cleared.add("alerts_$userId") }
        override suspend fun clearSavedScreeners(userId: String) { cleared.add("screeners_$userId") }
        override suspend fun clearUserSettings(userId: String) { cleared.add("settings_$userId") }
        override suspend fun clearOutbox(userId: String) { cleared.add("outbox_$userId"); outbox.removeAll { it.userId == userId } }
        override suspend fun clearCursor(userId: String) { cleared.add("cursor_$userId") }
    }

    class FakeSessionStore(private var uid: String? = "user1") : TokenSessionStore {
        override fun accessToken(): String? = "access_token"
        override fun refreshToken(): String? = "refresh_token"
        override fun replace(accessToken: String, refreshToken: String, userId: String) { uid = userId }
        override fun userId(): String? = uid
        override fun clear() { uid = null }
    }

    class FakeSyncApi : SyncApi {
        override suspend fun push(body: SyncPushRequest): Envelope<SyncPushResponse> {
            val results = body.operations.map {
                SyncResult(
                    operationId = it.operationId,
                    status = "ACCEPTED",
                    serverVersion = (it.baseVersion + 1),
                    cursor = 100L,
                    conflict = null
                )
            }
            return Envelope(SyncPushResponse(results))
        }

        override suspend fun changes(cursor: Long, limit: Int): Envelope<SyncChangesResponse> {
            return Envelope(
                SyncChangesResponse(
                    changes = emptyList(),
                    nextCursor = cursor,
                    hasMore = false,
                    serverTime = "2026-08-14T08:00:00Z"
                )
            )
        }

        override suspend fun bootstrap(): Envelope<SyncBootstrapResponse> {
            return Envelope(
                SyncBootstrapResponse(
                    watchlists = emptyList(),
                    items = emptyList(),
                    portfolios = listOf(mapOf("id" to "pf1", "name" to "Main PF", "version" to 1L)),
                    portfolioTransactions = listOf(mapOf("id" to "tx1", "portfolio_id" to "pf1", "version" to 1L)),
                    alertRules = emptyList(),
                    savedScreeners = emptyList(),
                    userSettings = emptyList(),
                    cursor = 42L
                )
            )
        }
    }

    @Test
    fun testCloudSyncManagerEnqueueAndPush() = kotlinx.coroutines.test.runTest {
        val dao = FakeSyncDao()
        val store = FakeSessionStore("user1")
        val api = FakeSyncApi()
        val manager = CloudSyncManager(api, dao, store)

        // 1. Enqueue outbox items for Portfolio, Alert, Screener, Settings
        manager.enqueue(SyncEntityTypes.PORTFOLIO, "pf1", "UPSERT", 0L, mapOf("name" to "Main"))
        manager.enqueue(SyncEntityTypes.ALERT_RULE, "ar1", "UPSERT", 0L, mapOf("name" to "Rule 1"))
        assertEquals(2, dao.outbox.size)

        // 2. Push pending outbox
        val results = manager.pushPending("dev1")
        assertEquals(2, results.size)
        assertEquals("ACCEPTED", results[0].status)
        assertEquals(0, dao.outbox.size)
    }

    @Test
    fun testCloudSyncManagerBootstrapAndAccountIsolation() = kotlinx.coroutines.test.runTest {
        val dao = FakeSyncDao()
        val store = FakeSessionStore("user1")
        val api = FakeSyncApi()
        val manager = CloudSyncManager(api, dao, store)

        // 1. Bootstrap
        manager.syncBootstrap()
        assertEquals(1, dao.portfolios.size)
        assertEquals(1, dao.transactions.size)

        // 2. Account Isolation Clear
        manager.clearAllUserData("user1")
        assertTrue(dao.cleared.contains("portfolios_user1"))
        assertTrue(dao.cleared.contains("transactions_user1"))
        assertTrue(dao.cleared.contains("outbox_user1"))
    }
}
