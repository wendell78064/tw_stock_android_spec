package tw.market.ledger.feature.watchlist.data

import java.io.IOException
import javax.inject.Inject
import tw.market.ledger.database.WatchlistDao
import tw.market.ledger.database.WatchlistEntity
import tw.market.ledger.database.WatchlistItemEntity
import tw.market.ledger.feature.watchlist.domain.WatchlistRepository
import tw.market.ledger.model.Watchlist
import tw.market.ledger.model.WatchlistDashboard
import tw.market.ledger.model.WatchlistItem
import tw.market.ledger.network.WatchlistAddInput
import tw.market.ledger.network.WatchlistApi
import tw.market.ledger.network.WatchlistItemDto
import tw.market.ledger.network.WatchlistItemInput
import tw.market.ledger.network.WatchlistNameInput
import tw.market.ledger.network.WatchlistOrderInput

class DefaultWatchlistRepository @Inject constructor(private val api: WatchlistApi, private val dao: WatchlistDao) : WatchlistRepository {
    override suspend fun dashboard(selectedId: String?): WatchlistDashboard = try {
        val groups = api.groups().data
        dao.clearGroups(); dao.upsertGroups(groups.map { WatchlistEntity(it.id, it.name, it.sortOrder) })
        val id = selectedId?.takeIf { value -> groups.any { it.id == value } } ?: groups.firstOrNull()?.id
        val items = id?.let { api.overview(it).data }.orEmpty()
        if (id != null) { dao.clearItems(id); dao.upsertItems(items.map(::entity)) }
        WatchlistDashboard(groups.map { Watchlist(it.id, it.name, it.sortOrder) }, id, items.map(::model))
    } catch (_: IOException) {
        val groups = dao.groups(); val id = selectedId ?: groups.firstOrNull()?.id
        WatchlistDashboard(groups.map { Watchlist(it.id, it.name, it.sortOrder) }, id, id?.let { dao.items(it).map(::model) }.orEmpty(), true)
    }
    override suspend fun create(name: String) { api.create(WatchlistNameInput(name.trim())) }
    override suspend fun rename(id: String, name: String) { api.rename(id, WatchlistNameInput(name.trim())) }
    override suspend fun delete(id: String) { api.delete(id) }
    override suspend fun reorderGroups(ids: List<String>) { api.reorderGroups(ids.mapIndexed { index, value -> WatchlistOrderInput(value, index) }) }
    override suspend fun add(id: String, code: String, market: String?) { api.add(id, WatchlistAddInput(code, market)) }
    override suspend fun edit(id: String, itemId: String, note: String?, target: String?, stop: String?, add: String?) { api.edit(id, itemId, WatchlistItemInput(note, target, stop, add)) }
    override suspend fun remove(id: String, itemId: String) { api.remove(id, itemId) }
    override suspend fun reorder(id: String, itemIds: List<String>) { api.reorderItems(id, itemIds.mapIndexed { index, value -> WatchlistOrderInput(value, index) }) }
}

private fun entity(it: WatchlistItemDto) = WatchlistItemEntity(it.watchlistId, it.id, it.securityCode, it.securityName, it.market, it.sortOrder, it.note, it.targetPrice, it.stopPrice, it.addPrice, it.close, it.change, it.changePercent, it.priceAsOf, it.dataStatus, it.foreignNet, it.marginBalanceChange, it.priceAboveMa20)
private fun model(it: WatchlistItemDto) = WatchlistItem(it.id, it.watchlistId, it.securityCode, it.securityName, it.market, it.sortOrder, it.note, it.targetPrice, it.stopPrice, it.addPrice, it.close, it.change, it.changePercent, it.priceAsOf, it.dataStatus, it.foreignNet, it.marginBalanceChange, it.priceAboveMa20)
private fun model(it: WatchlistItemEntity) = WatchlistItem(it.id, it.watchlistId, it.securityCode, it.securityName, it.market, it.sortOrder, it.note, it.targetPrice, it.stopPrice, it.addPrice, it.close, it.change, it.changePercent, it.priceAsOf, it.dataStatus, it.foreignNet, it.marginBalanceChange, it.priceAboveMa20)
