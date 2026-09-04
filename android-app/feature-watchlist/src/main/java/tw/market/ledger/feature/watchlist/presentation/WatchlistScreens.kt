package tw.market.ledger.feature.watchlist.presentation

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.watchlist.domain.WatchlistRepository
import tw.market.ledger.model.WatchlistDashboard
import tw.market.ledger.model.WatchlistItem
import tw.market.ledger.model.WatchlistSort
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeQuote
import tw.market.ledger.network.RealtimeSecurityTarget
import tw.market.ledger.network.RealtimeSubscriptionManager

sealed interface WatchlistUiState {
    data object Loading : WatchlistUiState
    data class Empty(val dashboard: WatchlistDashboard) : WatchlistUiState
    data class Success(val dashboard: WatchlistDashboard, val sort: WatchlistSort) : WatchlistUiState
    data class Offline(val dashboard: WatchlistDashboard) : WatchlistUiState
    data class Stale(val dashboard: WatchlistDashboard) : WatchlistUiState
    data class Partial(val dashboard: WatchlistDashboard) : WatchlistUiState
    data class Error(val message: String) : WatchlistUiState
}

@HiltViewModel
class WatchlistViewModel @Inject constructor(
    private val repository: WatchlistRepository,
    private val realtimeSubscriptions: RealtimeSubscriptionManager,
) : ViewModel() {
    private val mutableState = MutableStateFlow<WatchlistUiState>(WatchlistUiState.Loading)
    val state: StateFlow<WatchlistUiState> = mutableState
    private var selected: String? = null
    private var sort = WatchlistSort.MANUAL
    private var realtimeActive = false
    init {
        viewModelScope.launch {
            realtimeSubscriptions.latestQuotes.collect { quotes ->
                mutableState.value = mutableState.value.withRealtimeQuotes(quotes)
            }
        }
        refresh()
    }
    fun refresh(id: String? = selected) = viewModelScope.launch {
        mutableState.value = WatchlistUiState.Loading
        runCatching { repository.dashboard(id) }.onSuccess { dashboard ->
            selected = dashboard.selectedId
            if (realtimeActive && !dashboard.offline) {
                realtimeSubscriptions.updateWatchlistMembership(
                    dashboard.items.mapTo(mutableSetOf()) {
                        RealtimeSecurityTarget(it.market, it.securityCode)
                    }
                )
            }
            val current = dashboard.withRealtimeQuotes(realtimeSubscriptions.latestQuotes.value)
            mutableState.value = when {
                current.offline -> WatchlistUiState.Offline(current)
                current.items.isEmpty() -> WatchlistUiState.Empty(current)
                current.items.any { it.dataStatus == "PARTIAL" || it.dataStatus == "UNAVAILABLE" } -> WatchlistUiState.Partial(current)
                current.items.any { it.dataStatus == "STALE" } -> WatchlistUiState.Stale(current)
                else -> WatchlistUiState.Success(current.copy(items = sorted(current.items)), sort)
            }
        }.onFailure { mutableState.value = WatchlistUiState.Error(it.message ?: "載入失敗") }
    }
    fun setSort(value: WatchlistSort) { sort = value; refresh() }
    private fun sorted(items: List<WatchlistItem>) = when (sort) {
        WatchlistSort.MANUAL -> items.sortedBy { it.sortOrder }
        WatchlistSort.CODE -> items.sortedBy { it.securityCode }
        WatchlistSort.CHANGE_PERCENT -> items.sortedByDescending { it.changePercent?.toBigDecimalOrNull() }
        WatchlistSort.FOREIGN_NET -> items.sortedByDescending { it.foreignNet }
    }
    fun create(name: String) = mutate { repository.create(name) }
    fun rename(name: String) = mutate { selected?.let { repository.rename(it, name) } }
    fun delete() = mutate { selected?.let { repository.delete(it) }; selected = null }
    fun moveGroup(delta: Int, groups: List<tw.market.ledger.model.Watchlist>) = mutate {
        val ordered = groups.sortedBy { it.sortOrder }.toMutableList()
        val from = ordered.indexOfFirst { it.id == selected }
        val to = (from + delta).coerceIn(0, ordered.lastIndex)
        if (from >= 0 && from != to) {
            val moved = ordered.removeAt(from); ordered.add(to, moved)
            repository.reorderGroups(ordered.map { it.id })
        }
    }
    fun add(code: String, market: String?) = mutate { selected?.let { repository.add(it, code, market) } }
    fun edit(itemId: String, note: String?, target: String?, stop: String?, add: String?) = mutate { selected?.let { repository.edit(it, itemId, note, target, stop, add) } }
    fun remove(itemId: String) = mutate { selected?.let { repository.remove(it, itemId) } }
    fun move(item: WatchlistItem, delta: Int, all: List<WatchlistItem>) = mutate {
        val ordered = all.sortedBy { it.sortOrder }.toMutableList(); val from = ordered.indexOfFirst { it.id == item.id }
        val to = (from + delta).coerceIn(0, ordered.lastIndex); if (from >= 0 && from != to) { val moved = ordered.removeAt(from); ordered.add(to, moved); selected?.let { repository.reorder(it, ordered.map { row -> row.id }) } }
    }
    private fun mutate(block: suspend () -> Unit) = viewModelScope.launch { runCatching { block() }.onSuccess { refresh() }.onFailure { mutableState.value = WatchlistUiState.Error(it.message ?: "操作失敗") } }
    fun activateRealtime() {
        realtimeActive = true
        mutableState.value.dashboardOrNull()?.takeUnless { it.offline }?.let { dashboard ->
            realtimeSubscriptions.updateWatchlistMembership(
                dashboard.items.mapTo(mutableSetOf()) {
                    RealtimeSecurityTarget(it.market, it.securityCode)
                }
            )
        }
    }
    fun deactivateRealtime() {
        realtimeActive = false
        realtimeSubscriptions.releaseWatchlistMembership()
    }
    override fun onCleared() {
        deactivateRealtime()
        super.onCleared()
    }
}

private fun WatchlistUiState.dashboardOrNull(): WatchlistDashboard? = when (this) {
    is WatchlistUiState.Empty -> dashboard
    is WatchlistUiState.Success -> dashboard
    is WatchlistUiState.Offline -> dashboard
    is WatchlistUiState.Stale -> dashboard
    is WatchlistUiState.Partial -> dashboard
    else -> null
}

private fun WatchlistUiState.withRealtimeQuotes(quotes: Map<String, RealtimeQuote>): WatchlistUiState =
    when (this) {
        is WatchlistUiState.Empty -> copy(dashboard = dashboard.withRealtimeQuotes(quotes))
        is WatchlistUiState.Success -> copy(dashboard = dashboard.withRealtimeQuotes(quotes))
        is WatchlistUiState.Offline -> this
        is WatchlistUiState.Stale -> copy(dashboard = dashboard.withRealtimeQuotes(quotes))
        is WatchlistUiState.Partial -> copy(dashboard = dashboard.withRealtimeQuotes(quotes))
        else -> this
    }

private fun WatchlistDashboard.withRealtimeQuotes(quotes: Map<String, RealtimeQuote>): WatchlistDashboard =
    copy(items = items.map { item ->
        val quote = quotes["${item.market.uppercase()}:${item.securityCode.uppercase()}"]
        if (quote == null || quote.dataStatus == RealtimeDataStatus.UNAVAILABLE) item else item.copy(
            close = quote.lastPrice,
            change = quote.change ?: item.change,
            changePercent = quote.changePercent ?: item.changePercent,
            priceAsOf = quote.exchangeTimestamp,
            dataStatus = quote.dataStatus.name,
        )
    })

@Composable fun WatchlistRoute(onAlert: (WatchlistItem) -> Unit = {}, viewModel: WatchlistViewModel = hiltViewModel()) {
    DisposableEffect(viewModel) {
        viewModel.activateRealtime()
        onDispose(viewModel::deactivateRealtime)
    }
    val state by viewModel.state.collectAsState(); WatchlistScreen(state, viewModel, onAlert)
}

@Composable
fun WatchlistScreen(state: WatchlistUiState, viewModel: WatchlistViewModel? = null,
    onAlert: (WatchlistItem) -> Unit = {}) {
    when (state) {
        WatchlistUiState.Loading -> Text("Loading")
        is WatchlistUiState.Error -> Text(state.message)
        else -> {
            val dashboard = when (state) {
                is WatchlistUiState.Empty -> state.dashboard; is WatchlistUiState.Success -> state.dashboard
                is WatchlistUiState.Offline -> state.dashboard; is WatchlistUiState.Stale -> state.dashboard
                is WatchlistUiState.Partial -> state.dashboard; else -> error("unreachable")
            }
            Dashboard(dashboard, state, viewModel, onAlert)
        }
    }
}

@Composable private fun Dashboard(data: WatchlistDashboard, state: WatchlistUiState,
    vm: WatchlistViewModel?, onAlert: (WatchlistItem) -> Unit) {
    var groupsOpen by remember { mutableStateOf(false) }; var dialog by remember { mutableStateOf<String?>(null) }; var editing by remember { mutableStateOf<WatchlistItem?>(null) }
    Column(Modifier.fillMaxSize().padding(12.dp)) {
        if (state is WatchlistUiState.Offline) Text("OFFLINE · STALE")
        if (state is WatchlistUiState.Partial) Text("PARTIAL — 部分市場摘要無法取得")
        Row { OutlinedButton(onClick = { groupsOpen = true }) { Text(data.groups.firstOrNull { it.id == data.selectedId }?.name ?: "自選群組") }
            DropdownMenu(groupsOpen, { groupsOpen = false }) { data.groups.forEach { group -> DropdownMenuItem({ Text(group.name) }, { groupsOpen = false; vm?.refresh(group.id) }) } }
            TextButton({ dialog = "create" }) { Text("新增群組") }; TextButton({ dialog = "rename" }) { Text("改名") }; TextButton({ dialog = "delete" }) { Text("刪除") }
            TextButton({ vm?.moveGroup(-1, data.groups) }) { Text("群組上移") }; TextButton({ vm?.moveGroup(1, data.groups) }) { Text("群組下移") } }
        Row { TextButton({ dialog = "add" }) { Text("加入股票") }; WatchlistSort.entries.forEach { value -> TextButton({ vm?.setSort(value) }) { Text(value.name) } } }
        if (data.items.isEmpty()) Text("此自選群組尚無股票")
        LazyColumn { items(data.items, key = { it.id }) { row -> Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) { Column(Modifier.padding(10.dp)) {
            Text("${row.securityCode} ${row.securityName}"); Text("收盤 ${row.close ?: "--"}  ${row.change ?: "--"} (${row.changePercent ?: "--"}%)")
            Text("行情日期 ${row.priceAsOf ?: "--"}"); Text(if (row.priceAboveMa20 == true) "收盤高於 MA20" else "MA20 關係無資料")
            Row { TextButton({ editing = row }) { Text("編輯") }; TextButton({ onAlert(row) }) { Text("建立提醒") }; TextButton({ vm?.move(row, -1, data.items) }) { Text("上移") }; TextButton({ vm?.move(row, 1, data.items) }) { Text("下移") }; TextButton({ vm?.remove(row.id) }) { Text("移出") } }
        } } } }
    }
    dialog?.let { GroupDialog(it, { dialog = null }) { value -> when (it) { "create" -> vm?.create(value); "rename" -> vm?.rename(value); "delete" -> vm?.delete(); "add" -> vm?.add(value, null) }; dialog = null } }
    editing?.let { ItemDialog(it, { editing = null }) { note, target, stop, add -> vm?.edit(it.id, note, target, stop, add); editing = null } }
}

@Composable private fun GroupDialog(kind: String, dismiss: () -> Unit, confirm: (String) -> Unit) { var value by remember { mutableStateOf("") }; AlertDialog(onDismissRequest=dismiss, title={Text(if(kind=="delete") "確認刪除群組" else if(kind=="add") "加入股票" else "自選群組")}, text={if(kind!="delete") OutlinedTextField(value,{value=it},label={Text(if(kind=="add") "股票代號" else "名稱")})}, confirmButton={Button({confirm(value)}){Text("確認")}}, dismissButton={TextButton(dismiss){Text("取消")}}) }
@Composable private fun ItemDialog(item: WatchlistItem, dismiss: () -> Unit, confirm: (String?,String?,String?,String?)->Unit) { var note by remember { mutableStateOf(item.note.orEmpty()) }; var target by remember { mutableStateOf(item.targetPrice.orEmpty()) }; var stop by remember { mutableStateOf(item.stopPrice.orEmpty()) }; var add by remember { mutableStateOf(item.addPrice.orEmpty()) }; AlertDialog(onDismissRequest=dismiss,title={Text("編輯自選設定")},text={Column{OutlinedTextField(note,{note=it},label={Text("備註")});OutlinedTextField(target,{target=it},label={Text("目標價")});OutlinedTextField(stop,{stop=it},label={Text("停損價")});OutlinedTextField(add,{add=it},label={Text("加碼價")})}},confirmButton={Button({confirm(note.ifBlank{null},target.ifBlank{null},stop.ifBlank{null},add.ifBlank{null})}){Text("儲存")}},dismissButton={TextButton(dismiss){Text("取消")}}) }
