package tw.market.ledger.feature.watchlist

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
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

@OptIn(ExperimentalCoroutinesApi::class)
class WatchlistViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun before() = Dispatchers.setMain(dispatcher)
    @After fun after() = Dispatchers.resetMain()
    @Test fun `group switching sorting and mutations refresh`() = runTest(dispatcher) {
        val repo = FakeRepository(); val vm = WatchlistViewModel(repo); dispatcher.scheduler.advanceUntilIdle()
        vm.refresh("g"); vm.setSort(WatchlistSort.CODE); vm.create("測試"); vm.rename("新版"); vm.add("5678", "TWSE"); vm.edit("i", "n", "20", "8", "12"); vm.remove("i"); dispatcher.scheduler.advanceUntilIdle()
        assertEquals(listOf("create:測試", "rename:新版", "add:5678", "edit", "remove"), repo.calls)
    }
    @Test fun `empty offline stale and partial states are explicit`() = runTest(dispatcher) {
        val repo = FakeRepository(WatchlistDashboard(listOf(GROUP), "g", emptyList(), true)); val vm = WatchlistViewModel(repo); dispatcher.scheduler.advanceUntilIdle()
        assert(vm.state.value is WatchlistUiState.Offline)
        repo.dashboard = WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM.copy(dataStatus="STALE"))); vm.refresh(); dispatcher.scheduler.advanceUntilIdle(); assert(vm.state.value is WatchlistUiState.Stale)
        repo.dashboard = WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM.copy(dataStatus="PARTIAL"))); vm.refresh(); dispatcher.scheduler.advanceUntilIdle(); assert(vm.state.value is WatchlistUiState.Partial)
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class WatchlistComposeTest {
    @get:Rule val compose = createComposeRule()
    @Test fun `empty watchlist and group selector render`() { compose.setContent { WatchlistScreen(WatchlistUiState.Empty(WatchlistDashboard(listOf(GROUP), "g", emptyList()))) }; compose.onNodeWithText("我的自選").assertIsDisplayed(); compose.onNodeWithText("此自選群組尚無股票").assertIsDisplayed(); compose.onNodeWithText("加入股票").assertIsDisplayed() }
    @Test fun `row edit controls and partial state render`() { compose.setContent { WatchlistScreen(WatchlistUiState.Partial(WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM)))) }; compose.onNodeWithText("PARTIAL — 部分市場摘要無法取得").assertIsDisplayed(); compose.onNodeWithText("1234 測試股票").assertIsDisplayed(); compose.onNodeWithText("編輯").assertIsDisplayed(); compose.onNodeWithText("移出").assertIsDisplayed() }
    @Test fun `offline state renders stale marker`() { compose.setContent { WatchlistScreen(WatchlistUiState.Offline(WatchlistDashboard(listOf(GROUP), "g", listOf(ITEM), true))) }; compose.onNodeWithText("OFFLINE · STALE").assertIsDisplayed() }
}
