package tw.market.ledger.feature.portfolio.presentation

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import java.math.BigDecimal
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.portfolio.domain.*
import tw.market.ledger.model.*

sealed interface PortfolioUiState {
    data object Loading : PortfolioUiState
    data object Empty : PortfolioUiState
    data class Error(val message: String) : PortfolioUiState
    data class Offline(val dashboard: PortfolioDashboard) : PortfolioUiState
    data class Stale(val dashboard: PortfolioDashboard) : PortfolioUiState
    data class Partial(val dashboard: PortfolioDashboard) : PortfolioUiState
    data class Success(val dashboard: PortfolioDashboard) : PortfolioUiState
}

@HiltViewModel
class PortfolioViewModel @Inject constructor(private val repository: PortfolioRepository) : ViewModel() {
    private val _state = MutableStateFlow<PortfolioUiState>(PortfolioUiState.Loading)
    val state: StateFlow<PortfolioUiState> = _state.asStateFlow()
    val sort = MutableStateFlow(HoldingSort.MARKET_VALUE)
    init { refresh() }

    fun refresh() = viewModelScope.launch {
        _state.value = PortfolioUiState.Loading
        try {
            val result = repository.dashboard()
            _state.value = when {
                result.summary.fromCache -> PortfolioUiState.Offline(result)
                result.holdings.isEmpty() -> PortfolioUiState.Empty
                result.summary.dataStatus == DataStatus.STALE -> PortfolioUiState.Stale(result)
                result.summary.dataStatus == DataStatus.PARTIAL -> PortfolioUiState.Partial(result)
                else -> PortfolioUiState.Success(result)
            }
        } catch (error: IOException) {
            _state.value = PortfolioUiState.Error("目前離線，無法讀取持股快取")
        } catch (error: Exception) {
            _state.value = PortfolioUiState.Error(error.message ?: "持股載入失敗")
        }
    }

    fun setSort(value: HoldingSort) { sort.value = value }

    fun add(draft: TransactionDraft) = viewModelScope.launch {
        val dashboard = dashboard() ?: return@launch
        try {
            repository.addTransaction(dashboard.portfolio.id, draft); refresh()
        } catch (error: IOException) {
            _state.value = PortfolioUiState.Error("目前離線，無法修改交易")
        } catch (error: Exception) {
            _state.value = PortfolioUiState.Error(
                if (error.message.orEmpty().contains("422")) "賣出股數超過目前可用持股" else error.message ?: "交易失敗")
        }
    }

    fun delete(transactionId: String) = viewModelScope.launch {
        val dashboard = dashboard() ?: return@launch
        try { repository.deleteTransaction(dashboard.portfolio.id, transactionId); refresh() }
        catch (_: IOException) { _state.value = PortfolioUiState.Error("目前離線，無法修改交易") }
    }

    private fun dashboard(): PortfolioDashboard? = when (val value = state.value) {
        is PortfolioUiState.Success -> value.dashboard
        is PortfolioUiState.Partial -> value.dashboard
        is PortfolioUiState.Stale -> value.dashboard
        is PortfolioUiState.Offline -> value.dashboard
        else -> null
    }
}

@Composable
fun PortfolioRoute(
    onAdd: () -> Unit,
    onHolding: (PortfolioHolding) -> Unit,
    viewModel: PortfolioViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val sort by viewModel.sort.collectAsStateWithLifecycle()
    PortfolioDashboardScreen(state, sort, viewModel::setSort, onAdd, onHolding)
}

@Composable
fun AddTransactionRoute(onDone: () -> Unit, viewModel: PortfolioViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val holdings = when (val value = state) {
        is PortfolioUiState.Success -> value.dashboard.holdings
        is PortfolioUiState.Partial -> value.dashboard.holdings
        else -> emptyList()
    }
    AddTransactionScreen({ code -> holdings.firstOrNull { it.securityCode == code }?.quantityShares },
        { viewModel.add(it); onDone() }, onDone)
}

@Composable
fun HoldingDetailRoute(code: String, onSecurity: (PortfolioHolding) -> Unit,
    onAlert: (PortfolioHolding) -> Unit = {},
    viewModel: PortfolioViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val dashboard = when (val value = state) {
        is PortfolioUiState.Success -> value.dashboard
        is PortfolioUiState.Partial -> value.dashboard
        is PortfolioUiState.Stale -> value.dashboard
        is PortfolioUiState.Offline -> value.dashboard
        else -> null
    }
    val holding = dashboard?.holdings?.firstOrNull { it.securityCode == code }
    if (holding == null) Text("持股載入中") else HoldingDetailScreen(holding,
        dashboard.transactions, { onSecurity(holding) }, viewModel::delete, { onAlert(holding) })
}

@Composable
fun PortfolioDashboardScreen(
    state: PortfolioUiState,
    sort: HoldingSort = HoldingSort.MARKET_VALUE,
    onSort: (HoldingSort) -> Unit = {},
    onAdd: () -> Unit = {},
    onHolding: (PortfolioHolding) -> Unit = {},
) {
    when (state) {
        PortfolioUiState.Loading -> CircularProgressIndicator(Modifier.testTag("portfolio-loading"))
        PortfolioUiState.Empty -> Column(Modifier.padding(24.dp).testTag("portfolio-empty")) {
            Text("尚無持股"); Button(onClick = onAdd) { Text("新增第一筆交易") }
        }
        is PortfolioUiState.Error -> Text(state.message, Modifier.testTag("portfolio-error"))
        is PortfolioUiState.Offline -> Dashboard(state.dashboard, sort, onSort, onAdd, onHolding,
            "Offline / Stale：顯示最後快取")
        is PortfolioUiState.Stale -> Dashboard(state.dashboard, sort, onSort, onAdd, onHolding,
            "行情資料已過期")
        is PortfolioUiState.Partial -> Dashboard(state.dashboard, sort, onSort, onAdd, onHolding,
            "部分持股缺少可用行情")
        is PortfolioUiState.Success -> Dashboard(state.dashboard, sort, onSort, onAdd, onHolding, null)
    }
}

@Composable
private fun Dashboard(dashboard: PortfolioDashboard, sort: HoldingSort,
    onSort: (HoldingSort) -> Unit, onAdd: () -> Unit,
    onHolding: (PortfolioHolding) -> Unit, notice: String?) {
    val holdings = remember(dashboard.holdings, sort) { dashboard.holdings.sortedWith(
        when (sort) {
            HoldingSort.MARKET_VALUE -> compareByDescending { it.marketValue?.toBigDecimalOrNull() }
            HoldingSort.PNL -> compareByDescending { it.unrealizedPnl?.toBigDecimalOrNull() }
            HoldingSort.RETURN -> compareByDescending { it.unrealizedReturnPercent?.toBigDecimalOrNull() }
            HoldingSort.CODE -> compareBy { it.securityCode }
        }) }
    LazyColumn(Modifier.fillMaxSize().padding(12.dp).testTag("portfolio-dashboard"),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Text("總市值 ${dashboard.summary.totalMarketValue ?: "--"}")
            Text("總成本 ${dashboard.summary.totalCostBasis}")
            Text("未實現 ${dashboard.summary.totalUnrealizedPnl ?: "--"}　已實現 ${dashboard.summary.totalRealizedPnl}")
            Text("報酬率 ${dashboard.summary.totalReturnPercent ?: "--"}%")
            Text("行情 ${dashboard.summary.priceAsOf ?: "未提供"} · ${dashboard.summary.dataStatus}")
            Text("損益未包含交易稅")
            notice?.let { Text(it) }
            Button(onClick = onAdd, modifier = Modifier.testTag("add-transaction")) { Text("新增交易") }
        }
        item { Row { HoldingSort.entries.forEach { value ->
            FilterChip(selected = sort == value, onClick = { onSort(value) },
                label = { Text(value.name) }) } } }
        items(holdings, key = { "${it.market}-${it.securityCode}" }) { holding ->
            Card(onClick = { onHolding(holding) }, modifier = Modifier.fillMaxWidth()
                .testTag("holding-${holding.securityCode}")) { Column(Modifier.padding(12.dp)) {
                Text("${holding.securityCode} ${holding.securityName}")
                Text("${holding.quantityShares} 股 · 均價 ${holding.averageCost ?: "--"}")
                Text("收盤 ${holding.latestPrice ?: "--"} · 市值 ${holding.marketValue ?: "--"}")
                Text("損益 ${holding.unrealizedPnl ?: "--"} · ${holding.unrealizedReturnPercent ?: "--"}%")
                LinearProgressIndicator(progress = { (holding.allocationPercent?.toFloatOrNull() ?: 0f) / 100f })
            } }
        }
    }
}

data class TransactionFormState(
    val code: String = "",
    val side: TransactionSide = TransactionSide.BUY,
    val executedAt: String = "",
    val quantity: String = "",
    val price: String = "",
    val fee: String = "0",
    val lotType: LotType = LotType.ROUND_LOT,
)

fun TransactionFormState.error(availableShares: Long? = null): String? = when {
    code.isBlank() -> "請選擇股票"
    runCatching { java.time.OffsetDateTime.parse(executedAt) }.isFailure -> "請輸入有效日期時間"
    quantity.toLongOrNull()?.let { it > 0 } != true -> "股數必須大於 0"
    price.toBigDecimalOrNull()?.let { it > BigDecimal.ZERO } != true -> "成交價格必須大於 0"
    fee.toBigDecimalOrNull()?.let { it >= BigDecimal.ZERO } != true -> "手續費不可小於 0"
    side == TransactionSide.SELL && availableShares != null && quantity.toLong() > availableShares ->
        "賣出股數超過目前可用持股"
    else -> null
}

@Composable
fun AddTransactionScreen(availableShares: (String) -> Long? = { null }, onSave: (TransactionDraft) -> Unit,
    onCancel: () -> Unit) {
    var form by remember { mutableStateOf(TransactionFormState()) }
    val error = form.error(availableShares(form.code))
    Column(Modifier.padding(16.dp).testTag("add-transaction-screen"),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(form.code, { form = form.copy(code=it) }, label={Text("股票代號")})
        Row { TransactionSide.entries.forEach { side -> FilterChip(form.side == side,
            { form=form.copy(side=side) }, { Text(side.name) }) } }
        OutlinedTextField(form.executedAt, { form=form.copy(executedAt=it) }, label={Text("日期時間")})
        OutlinedTextField(form.quantity, { form=form.copy(quantity=it) }, label={Text("股數")})
        OutlinedTextField(form.price, { form=form.copy(price=it) }, label={Text("成交價格")})
        OutlinedTextField(form.fee, { form=form.copy(fee=it) }, label={Text("手續費")})
        Row { LotType.entries.forEach { lot -> FilterChip(form.lotType == lot,
            { form=form.copy(lotType=lot) }, { Text(lot.name) }) } }
        error?.let { Text(it, color=MaterialTheme.colorScheme.error, modifier=Modifier.testTag("transaction-validation")) }
        Row { Button(enabled=error == null, onClick={ onSave(TransactionDraft(form.code, null,
            form.side, form.executedAt, form.quantity.toLong(), form.price, form.fee, form.lotType)) }) {
            Text("Save") }; TextButton(onClick=onCancel) { Text("Cancel") } }
    }
}

@Composable
fun HoldingDetailScreen(holding: PortfolioHolding, transactions: List<PortfolioTransaction>,
    onSecurity: () -> Unit, onDelete: (String) -> Unit, onAlert: () -> Unit = {}) {
    var pending by remember { mutableStateOf<String?>(null) }
    LazyColumn(Modifier.padding(12.dp).testTag("holding-detail")) {
        item { Text("${holding.securityCode} ${holding.securityName}")
            Text("${holding.quantityShares} 股 · 均價 ${holding.averageCost ?: "--"}")
            Text("成本 ${holding.costBasis} · 收盤 ${holding.latestPrice ?: "--"}")
            Text("市值 ${holding.marketValue ?: "--"} · 未實現 ${holding.unrealizedPnl ?: "--"}")
            Text("已實現 ${holding.realizedPnl} · 報酬 ${holding.unrealizedReturnPercent ?: "--"}%")
            Row { TextButton(onClick=onSecurity) { Text("查看個股") }
                TextButton(onClick=onAlert) { Text("建立提醒") } } }
        items(transactions.filter { it.securityCode == holding.securityCode }) { item ->
            ListItem(headlineContent={Text("${item.side} ${item.quantityShares} 股 @ ${item.price}")},
                supportingContent={Text("${item.executedAt} · fee ${item.fee} · ${item.lotType}")},
                trailingContent={TextButton(onClick={pending=item.id}) { Text("Delete") }})
        }
    }
    if (pending != null) AlertDialog(onDismissRequest={pending=null}, title={Text("刪除交易？")},
        text={Text("刪除後將重新計算後續持股與損益。")}, confirmButton={TextButton(onClick={
            pending?.let(onDelete); pending=null }) { Text("確認刪除") }},
        dismissButton={TextButton(onClick={pending=null}) { Text("取消") }})
}
