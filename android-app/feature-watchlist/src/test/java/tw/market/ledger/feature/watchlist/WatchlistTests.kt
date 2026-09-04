package tw.market.ledger.feature.watchlist

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.lifecycle.ViewModelStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import tw.market.ledger.feature.watchlist.domain.WatchlistRepository
import tw.market.ledger.feature.watchlist.presentation.WatchlistScreen
import tw.market.ledger.feature.watchlist.presentation.WatchlistUiState
import tw.market.ledger.feature.watchlist.presentation.WatchlistViewModel
import tw.market.ledger.model.Watchlist
import tw.market.ledger.model.WatchlistDashboard
import tw.market.ledger.model.WatchlistItem
import tw.market.ledger.model.WatchlistSort
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeQuote
import tw.market.ledger.network.RealtimeQuoteType
import tw.market.ledger.network.RealtimeSubscriptionClient
import tw.market.ledger.network.RealtimeSubscriptionManager

private val GROUP = Watchlist("g", "我的自選", 0)
private val ITEM = WatchlistItem("i", "g", "1234", "測試股票", "TWSE", 0, close="10", change="1", changePercent="11.11", priceAsOf="2026-08-11", dataStatus="FINAL", foreignNet=100, priceAboveMa20=true)

private class FakeRepository(var dashboard: WatchlistDashboard = WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM))) : WatchlistRepository {
    val calls = mutableListOf<String>()
    override suspend fun dashboard(selectedId: String?) = dashboard.copy(selectedId = selectedId ?: dashboard.selectedId)
    override suspend fun create(name: String) { calls += "create:$name" }
    override suspend fun rename(id: String, name: String) { calls += "rename:$name" }
    override suspend fun delete(id: String) { calls += "delete" }
    override suspend fun reorderGroups(ids: List<String>) { calls += "groups-reorder" }
    override suspend fun add(id: String, code: String, market: String?) { calls += "add:$code" }
    override suspend fun edit(id: String, itemId: String, note: String?, target: String?, stop: String?, add: String?) { calls += "edit" }
    override suspend fun remove(id: String, itemId: String) { calls += "remove" }
    override suspend fun reorder(id: String, itemIds: List<String>) { calls += "reorder" }
}

private class FakeRealtimeClient : RealtimeSubscriptionClient {
    data class Call(val action: String, val market: String, val code: String, val types: Set<RealtimeQuoteType>)
    private val mutableQuotes = MutableSharedFlow<RealtimeQuote>(replay = 1)
    override val quotesFlow: SharedFlow<RealtimeQuote> = mutableQuotes
    val calls = mutableListOf<Call>()
    override fun connect() = Unit
    override fun subscribe(market: String, code: String, quoteTypes: Set<RealtimeQuoteType>) {
        calls += Call("subscribe", market, code, quoteTypes)
    }
    override fun unsubscribe(market: String, code: String, quoteTypes: Set<RealtimeQuoteType>) {
        calls += Call("unsubscribe", market, code, quoteTypes)
    }
    fun emit(quote: RealtimeQuote) = mutableQuotes.tryEmit(quote)
}

@OptIn(ExperimentalCoroutinesApi::class)
class WatchlistViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun before() = Dispatchers.setMain(dispatcher)
    @After fun after() = Dispatchers.resetMain()
    @Test fun `group switching sorting and mutations refresh`() = runTest(dispatcher) {
        val repo = FakeRepository(); val vm = WatchlistViewModel(repo, manager()); dispatcher.scheduler.advanceUntilIdle()
        vm.refresh("g"); vm.setSort(WatchlistSort.CODE); vm.create("測試"); vm.rename("新版"); vm.add("5678", "TWSE"); vm.edit("i", "n", "20", "8", "12"); vm.remove("i"); dispatcher.scheduler.advanceUntilIdle()
        assertEquals(listOf("create:測試", "rename:新版", "add:5678", "edit", "remove"), repo.calls)
    }
    @Test fun `empty offline stale and partial states are explicit`() = runTest(dispatcher) {
        val repo = FakeRepository(WatchlistDashboard(listOf(GROUP), "g", emptyList(), true)); val vm = WatchlistViewModel(repo, manager()); dispatcher.scheduler.advanceUntilIdle()
        assert(vm.state.value is WatchlistUiState.Offline)
        repo.dashboard = WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM.copy(dataStatus="STALE"))); vm.refresh(); dispatcher.scheduler.advanceUntilIdle(); assert(vm.state.value is WatchlistUiState.Stale)
        repo.dashboard = WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM.copy(dataStatus="PARTIAL"))); vm.refresh(); dispatcher.scheduler.advanceUntilIdle(); assert(vm.state.value is WatchlistUiState.Partial)
    }
    @Test fun `selected group owns tick and viewmodel cleanup releases it`() = runTest(dispatcher) {
        val client = FakeRealtimeClient()
        val subscriptions = RealtimeSubscriptionManager(
            client,
            scope = backgroundScope,
            watchlistRealtimeEnabled = true,
        )
        val store = ViewModelStore()
        val viewModel = WatchlistViewModel(FakeRepository(), subscriptions)
        store.put("watchlist", viewModel)
        viewModel.activateRealtime()
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(listOf(FakeRealtimeClient.Call("subscribe", "TWSE", "1234", setOf(RealtimeQuoteType.TICK))), client.calls)
        store.clear()
        assertEquals("unsubscribe", client.calls.last().action)
        assertEquals(setOf(RealtimeQuoteType.TICK), client.calls.last().types)
    }
    @Test fun `group change set diffs membership and live quote updates row`() = runTest(dispatcher) {
        val client = FakeRealtimeClient()
        val managerScope = CoroutineScope(dispatcher + Job())
        val subscriptions = RealtimeSubscriptionManager(
            client,
            scope = managerScope,
            watchlistRealtimeEnabled = true,
        )
        val repository = FakeRepository()
        val vm = WatchlistViewModel(repository, subscriptions)
        vm.activateRealtime()
        dispatcher.scheduler.advanceUntilIdle()

        client.emit(
            RealtimeQuote(
                securityId = "security-1234",
                marketId = "TWSE",
                code = "1234",
                exchangeTimestamp = "2026-09-04T01:00:00Z",
                receivedAt = "2026-09-04T01:00:00Z",
                lastPrice = "12.5",
                change = "2.5",
                changePercent = "25",
                dataStatus = RealtimeDataStatus.LIVE,
            )
        )
        dispatcher.scheduler.advanceUntilIdle()
        val live = (vm.state.value as WatchlistUiState.Success).dashboard.items.single()
        assertEquals("12.5", live.close)
        assertEquals("LIVE", live.dataStatus)

        repository.dashboard = WatchlistDashboard(
            listOf(GROUP, Watchlist("g2", "第二群組", 1)),
            "g2",
            listOf(ITEM.copy(id = "i2", watchlistId = "g2", securityCode = "2454")),
        )
        vm.refresh("g2")
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals("unsubscribe", client.calls[1].action)
        assertEquals("1234", client.calls[1].code)
        assertEquals("subscribe", client.calls[2].action)
        assertEquals("2454", client.calls[2].code)
        managerScope.cancel()
    }
    private fun manager() = RealtimeSubscriptionManager(FakeRealtimeClient())
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class WatchlistComposeTest {
    @get:Rule val compose = createComposeRule()
    @Test fun `empty watchlist and group selector render`() { compose.setContent { WatchlistScreen(WatchlistUiState.Empty(WatchlistDashboard(listOf(GROUP), "g", emptyList()))) }; compose.onNodeWithText("我的自選").assertIsDisplayed(); compose.onNodeWithText("此自選群組尚無股票").assertIsDisplayed(); compose.onNodeWithText("加入股票").assertIsDisplayed() }
    @Test fun `row edit controls and partial state render`() { compose.setContent { WatchlistScreen(WatchlistUiState.Partial(WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM)))) }; compose.onNodeWithText("PARTIAL — 部分市場摘要無法取得").assertIsDisplayed(); compose.onNodeWithText("1234 測試股票").assertIsDisplayed(); compose.onNodeWithText("編輯").assertIsDisplayed(); compose.onNodeWithText("移出").assertIsDisplayed() }
    @Test fun `offline state renders stale marker`() { compose.setContent { WatchlistScreen(WatchlistUiState.Offline(WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM), true))) }; compose.onNodeWithText("OFFLINE · STALE").assertIsDisplayed() }
}
