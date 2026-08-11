package tw.market.ledger.feature.alert.presentation

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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
import tw.market.ledger.feature.alert.domain.AlertRepository
import tw.market.ledger.model.AlertDashboard
import tw.market.ledger.model.AlertEvent
import tw.market.ledger.model.AlertRule
import tw.market.ledger.model.AlertScope
import tw.market.ledger.model.AlertType
import tw.market.ledger.network.AlertRuleInput

sealed interface AlertUiState {
    data object Loading : AlertUiState
    data class Success(val data: AlertDashboard) : AlertUiState
    data class Offline(val data: AlertDashboard) : AlertUiState
    data class Error(val message: String) : AlertUiState
}

@HiltViewModel
class AlertViewModel @Inject constructor(private val repo: AlertRepository) : ViewModel() {
    private val mutableState = MutableStateFlow<AlertUiState>(AlertUiState.Loading)
    val state: StateFlow<AlertUiState> = mutableState
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        runCatching { repo.dashboard() }.onSuccess {
            mutableState.value = if (it.offline) AlertUiState.Offline(it) else AlertUiState.Success(it)
        }.onFailure { mutableState.value = AlertUiState.Error(it.message ?: "載入失敗") }
    }
    fun save(input: AlertRuleInput, id: String? = null) = mutate { if (id == null) repo.create(input) else repo.edit(id, input) }
    fun delete(id: String) = mutate { repo.delete(id) }
    fun toggle(id: String, value: Boolean) = mutate { repo.toggle(id, value) }
    fun read(id: String) = mutate { repo.read(id) }
    fun readAll() = mutate { repo.readAll() }
    private fun mutate(block: suspend () -> Unit) = viewModelScope.launch {
        runCatching { block() }.onSuccess { refresh() }
            .onFailure { mutableState.value = AlertUiState.Error(it.message ?: "操作失敗") }
    }
}

@Composable fun AlertRulesRoute(onCreate: () -> Unit = {}, vm: AlertViewModel = hiltViewModel()) {
    val state by vm.state.collectAsState()
    AlertRulesScreen(state, onCreate, { vm.toggle(it.id, !it.enabled) }, { vm.delete(it.id) })
}
@Composable fun NotificationCenterRoute(vm: AlertViewModel = hiltViewModel()) {
    val state by vm.state.collectAsState(); NotificationCenterScreen(state, { vm.read(it.id) }, vm::readAll)
}
@Composable fun CreateAlertRoute(prefillSecurity: String? = null, prefillPrice: String? = null,
    initialType: AlertType = AlertType.PRICE_TARGET, onDone: () -> Unit = {},
    vm: AlertViewModel = hiltViewModel()) {
    CreateAlertScreen(prefillSecurity, prefillPrice, initialType) { vm.save(it); onDone() }
}

@Composable
fun AlertRulesScreen(state: AlertUiState, onCreate: () -> Unit = {}, toggle: (AlertRule) -> Unit = {}, delete: (AlertRule) -> Unit = {}) {
    val data = state.dashboardOrNull()
    if (state is AlertUiState.Loading) return Text("Loading")
    if (state is AlertUiState.Error) return Text(state.message)
    Column(Modifier.padding(12.dp)) {
        if (state is AlertUiState.Offline) Text("OFFLINE · STALE")
        Text("提醒規則"); Button(onCreate) { Text("建立提醒") }
        LazyColumn { items(data!!.rules) { rule -> Card(Modifier.fillMaxWidth().padding(4.dp)) {
            Column(Modifier.padding(8.dp)) { Text(rule.name); Text("${rule.scope} · ${rule.type}"); Text(if (rule.enabled) "Enabled" else "Disabled")
                Row { TextButton({ toggle(rule) }) { Text(if (rule.enabled) "Disable" else "Enable") }; TextButton({ delete(rule) }) { Text("Delete") } }
            }
        } } }
    }
}

@Composable
fun CreateAlertScreen(prefillSecurity: String? = null, prefillPrice: String? = null, initialType: AlertType = AlertType.PRICE_TARGET, onSave: (AlertRuleInput) -> Unit = {}) {
    var type by remember { mutableStateOf(initialType) }; var scope by remember { mutableStateOf(AlertScope.SECURITY) }
    var name by remember { mutableStateOf("") }; var threshold by remember { mutableStateOf(prefillPrice.orEmpty()) }
    var scopeTarget by remember { mutableStateOf(prefillSecurity.orEmpty()) }
    var ma by remember { mutableStateOf("20") }; var percent by remember { mutableStateOf("1") }; var days by remember { mutableStateOf("3") }; var error by remember { mutableStateOf<String?>(null) }
    Column(Modifier.padding(12.dp)) {
        Text("建立提醒"); OutlinedTextField(name, { name = it }, label = { Text("名稱") })
        Row { AlertScope.entries.forEach { value -> TextButton({ scope = value }) { Text(value.name) } } }
        OutlinedTextField(scopeTarget, { scopeTarget = it }, label = { Text("${scope.name} ID") })
        AlertType.entries.forEach { value -> TextButton({ type = value }) { Text(value.name) } }
        if (type.name.startsWith("PRICE")) OutlinedTextField(threshold, { threshold = it }, label = { Text("設定價格") })
        else { OutlinedTextField(ma, { ma = it }, label = { Text("MA Period") }); if (type == AlertType.MA_NEAR) OutlinedTextField(percent, { percent = it }, label = { Text("距離 %") }); if (type.name.contains("CONSECUTIVE")) OutlinedTextField(days, { days = it }, label = { Text("交易日數") }) }
        error?.let { Text(it) }
        Button({
            val period = ma.toIntOrNull(); val invalid = name.isBlank() || scopeTarget.isBlank() || type.name.startsWith("PRICE") && threshold.toBigDecimalOrNull() == null || type.name.startsWith("MA") && period !in setOf(5, 10, 20, 60, 120, 240)
            if (invalid) error = "欄位設定無效" else onSave(AlertRuleInput(name, type.name, scope.name, securityId = scopeTarget.takeIf { scope == AlertScope.SECURITY }, portfolioId = scopeTarget.takeIf { scope == AlertScope.PORTFOLIO }, watchlistId = scopeTarget.takeIf { scope == AlertScope.WATCHLIST }, maPeriod = period.takeIf { type.name.startsWith("MA") }, thresholdPrice = threshold.takeIf { type.name.startsWith("PRICE") }, thresholdPercent = percent.takeIf { type == AlertType.MA_NEAR }, consecutiveDays = days.toIntOrNull().takeIf { type.name.contains("CONSECUTIVE") }))
        }) { Text("Save") }
    }
}

@Composable
fun NotificationCenterScreen(state: AlertUiState, read: (AlertEvent) -> Unit = {}, readAll: () -> Unit = {}) {
    val data = state.dashboardOrNull()
    if (state is AlertUiState.Loading) return Text("Loading")
    if (state is AlertUiState.Error) return Text(state.message)
    Column(Modifier.padding(12.dp)) { Text("通知中心"); Text("未讀 ${data!!.events.count { it.readAt == null }}"); TextButton(readAll) { Text("全部已讀") }
        LazyColumn { items(data.events) { event -> Card(Modifier.fillMaxWidth().padding(4.dp)) { Column(Modifier.padding(8.dp)) {
            val readLabel = if (event.readAt == null) "未讀" else "已讀"; Text("$readLabel ${event.securityCode} ${event.securityName}"); Text(event.message)
            Text("收盤 ${event.triggerPrice} · ${event.referenceType} ${event.referenceValue}"); Text("資料日 ${event.tradeDate} · ${event.dataStatus}"); TextButton({ read(event) }) { Text("標記已讀") }
        } } } }
    }
}
private fun AlertUiState.dashboardOrNull() = when (this) { is AlertUiState.Success -> data; is AlertUiState.Offline -> data; else -> null }
