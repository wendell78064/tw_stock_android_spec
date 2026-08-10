package tw.market.ledger.feature.market.presentation

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.market.domain.GetMarketOverviewUseCase
import tw.market.ledger.feature.market.domain.MarketRepository
import tw.market.ledger.model.*

sealed interface MarketDashboardUiState {
    data object Loading : MarketDashboardUiState
    data object Empty : MarketDashboardUiState
    data class Error(val message: String) : MarketDashboardUiState
    data class Offline(val overview: MarketOverview) : MarketDashboardUiState
    data class Partial(val overview: MarketOverview) : MarketDashboardUiState
    data class Success(val overview: MarketOverview) : MarketDashboardUiState
}

@HiltViewModel
class MarketDashboardViewModel @Inject constructor(private val overview: GetMarketOverviewUseCase,
    private val repository: MarketRepository) : ViewModel() {
    private val _uiState = MutableStateFlow<MarketDashboardUiState>(MarketDashboardUiState.Loading)
    val uiState: StateFlow<MarketDashboardUiState> = _uiState.asStateFlow()
    val window = MutableStateFlow(1)
    val institutional = MutableStateFlow<List<InstitutionalPoint>>(emptyList())
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        _uiState.value = MarketDashboardUiState.Loading
        try {
            val result = overview()
            _uiState.value = when { result.indexes.isEmpty() -> MarketDashboardUiState.Empty
                result.fromCache -> MarketDashboardUiState.Offline(result)
                result.dataStatus == DataStatus.PARTIAL -> MarketDashboardUiState.Partial(result)
                else -> MarketDashboardUiState.Success(result) }
            selectWindow(window.value)
        } catch (error: IOException) { _uiState.value = MarketDashboardUiState.Error("目前離線且沒有市場快取") }
        catch (error: Exception) { _uiState.value = MarketDashboardUiState.Error(error.message ?: "市場載入失敗") }
    }
    fun selectWindow(value: Int) = viewModelScope.launch {
        window.value = value
        try { institutional.value = repository.marketInstitutional(MarketCode.TWSE, value) }
        catch (_: IOException) { /* overview remains visible and stale */ }
    }
}

@Composable fun MarketDashboardRoute(viewModel: MarketDashboardViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle(); val window by viewModel.window.collectAsStateWithLifecycle()
    val institutions by viewModel.institutional.collectAsStateWithLifecycle()
    MarketDashboardScreen(state, window, institutions, viewModel::selectWindow)
}

@Composable fun MarketDashboardScreen(state: MarketDashboardUiState, window: Int,
    institutions: List<InstitutionalPoint> = emptyList(), onWindow: (Int) -> Unit = {}) {
    when (state) {
        MarketDashboardUiState.Loading -> Box(Modifier.fillMaxSize()) { CircularProgressIndicator(Modifier.testTag("market-loading")) }
        MarketDashboardUiState.Empty -> Text("目前沒有市場資料", Modifier.testTag("market-empty"))
        is MarketDashboardUiState.Error -> Text("市場載入失敗：${state.message}", Modifier.testTag("market-error"))
        is MarketDashboardUiState.Offline -> Dashboard(state.overview, window, institutions, onWindow, "Offline / Stale：顯示 ${state.overview.asOf} 快取")
        is MarketDashboardUiState.Partial -> Dashboard(state.overview, window, institutions, onWindow, "Partial：部分盤後資料尚未公布")
        is MarketDashboardUiState.Success -> Dashboard(state.overview, window, institutions, onWindow, null)
    }
}

@Composable private fun Dashboard(data: MarketOverview, window: Int, institutions: List<InstitutionalPoint>,
    onWindow: (Int) -> Unit, notice: String?) {
    LazyColumn(Modifier.fillMaxSize().padding(12.dp).testTag("market-dashboard"),
        verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("資料狀態：${data.dataStatus}"); notice?.let { Text(it) } }
        items(data.indexes.size) { IndexCard(data.indexes[it]) }
        item { Text("市場廣度", style = MaterialTheme.typography.titleMedium) }
        items(data.breadth.size) { BreadthCard(data.breadth[it]) }
        item {
            Text("三大法人現貨", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) { listOf(1,5,10,20,60).forEach {
                FilterChip(selected = window == it, onClick = { onWindow(it) }, label = { Text(if (it == 1) "今日" else "${it}日") }) } }
            (if (institutions.isEmpty()) data.institutional else institutions).takeLast(6).forEach {
                Text("${it.institutionType} ${it.dealerSubtype ?: ""} 買 ${it.buy ?: "--"} 賣 ${it.sell ?: "--"} 淨 ${it.net ?: "--"}") }
        }
        item { Text("融資／融券", style = MaterialTheme.typography.titleMedium); data.margins.lastOrNull()?.let {
            Text("融資餘額 ${it.marginBalance ?: "--"}（${it.marginBalanceChange ?: "--"}）")
            Text("融券餘額 ${it.shortBalance ?: "--"}（${it.shortBalanceChange ?: "--"}） 券資比 ${it.shortMarginRatio ?: "--"}") } }
        item { Text("借券", style = MaterialTheme.typography.titleMedium); data.lending.lastOrNull()?.let {
            Text("賣出 ${it.lendingSell ?: "--"} 餘額 ${it.lendingBalance ?: "--"}（${it.lendingBalanceChange ?: "--"}）") } }
        item { Text("資料更新時間：${data.asOf ?: "未提供"}") }
    }
}

@Composable fun IndexCard(item: MarketIndex) { Card(Modifier.fillMaxWidth().testTag("index-${item.code}")) {
    Column(Modifier.padding(12.dp)) { val sign = if ((item.change?.toBigDecimalOrNull()?.signum() ?: 0) >= 0) "+" else ""
        Text(item.name, style = MaterialTheme.typography.titleMedium); Text(item.close ?: "--")
        Text("$sign${item.change ?: "--"}（$sign${item.changePercent ?: "--"}%）")
        Text("開 ${item.open ?: "--"} 高 ${item.high ?: "--"} 低 ${item.low ?: "--"}")
        Text("成交金額 ${item.turnoverAmount ?: "--"} · ${item.tradeDate} · ${item.dataStatus}") } } }

@Composable fun BreadthCard(item: MarketBreadth) { Card(Modifier.fillMaxWidth().testTag("breadth-${item.market}")) {
    Column(Modifier.padding(12.dp)) { Text(item.market.name); Text("上漲 ${item.advancers ?: "--"}　下跌 ${item.decliners ?: "--"}　平盤 ${item.unchanged ?: "--"}")
        Text("漲停 ${item.limitUp ?: "--"}　跌停 ${item.limitDown ?: "--"}")
        val up = item.advancers ?: 0; val down = item.decliners ?: 0
        Canvas(Modifier.fillMaxWidth().height(8.dp)) { val ratio = if (up + down == 0) 0f else up.toFloat()/(up+down)
            drawRect(Color.Red, size = size.copy(width = size.width * ratio)); drawRect(Color(0xFF008000), topLeft = androidx.compose.ui.geometry.Offset(size.width*ratio,0f)) } } } }
