package tw.market.ledger.feature.watchlist.domain

import tw.market.ledger.model.WatchlistDashboard

interface WatchlistRepository {
    suspend fun dashboard(selectedId: String? = null): WatchlistDashboard
    suspend fun create(name: String)
    suspend fun rename(id: String, name: String)
    suspend fun delete(id: String)
    suspend fun reorderGroups(ids: List<String>)
    suspend fun add(id: String, code: String, market: String? = null)
    suspend fun edit(id: String, itemId: String, note: String?, target: String?, stop: String?, add: String?)
    suspend fun remove(id: String, itemId: String)
    suspend fun reorder(id: String, itemIds: List<String>)
}
