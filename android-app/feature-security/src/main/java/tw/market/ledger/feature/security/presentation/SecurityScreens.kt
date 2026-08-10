package tw.market.ledger.feature.security.presentation

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.FilterChip
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security
import tw.market.ledger.model.Candle
import tw.market.ledger.model.ChartRange
import tw.market.ledger.model.PriceBasis
import tw.market.ledger.model.TechnicalPoint

@Composable
fun SecuritySearchRoute(
    onSecurityClick: (Security) -> Unit,
    viewModel: SecuritySearchViewModel = hiltViewModel(),
) {
    val query by viewModel.query.collectAsStateWithLifecycle()
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    SecuritySearchScreen(
        query = query, state = state, onQueryChange = viewModel::onQueryChange,
        onClear = viewModel::onClear, onSearch = viewModel::onSearch,
        onSecurityClick = onSecurityClick,
    )
}

@Composable
fun SecuritySearchScreen(
    query: String,
    state: SecuritySearchUiState,
    onQueryChange: (String) -> Unit,
    onClear: () -> Unit,
    onSearch: () -> Unit,
    onSecurityClick: (Security) -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        OutlinedTextField(
            value = query, onValueChange = onQueryChange, modifier = Modifier.fillMaxWidth().testTag("security-search-input"),
            label = { Text("輸入至少 2 個字元的股票代號或公司名稱") }, singleLine = true,
            trailingIcon = { if (query.isNotEmpty()) TextButton(onClick = onClear) { Text("清除") } },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { onSearch() }),
        )
        when (state) {
            SecuritySearchUiState.Idle -> Text("請輸入股票代號或公司名稱")
            SecuritySearchUiState.Loading -> CircularProgressIndicator(Modifier.testTag("search-loading"))
            SecuritySearchUiState.Empty -> Text("找不到符合的上市／上櫃普通股")
            is SecuritySearchUiState.Error -> StateMessage("搜尋失敗：${state.message}")
            is SecuritySearchUiState.Offline -> StateMessage(state.message)
            is SecuritySearchUiState.Stale -> {
                Text("離線快取資料 · 最後更新 ${state.asOf}")
                SecurityResults(state.items, onSecurityClick)
            }
            is SecuritySearchUiState.Success -> {
                Text("最後更新 ${state.asOf}")
                SecurityResults(state.items, onSecurityClick)
            }
        }
    }
}

@Composable
private fun StateMessage(message: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(message)
        Text("可確認網路後重新搜尋")
    }
}

@Composable
private fun SecurityResults(items: List<Security>, onClick: (Security) -> Unit) {
    LazyColumn(Modifier.testTag("security-results")) {
        items(items, key = { "${it.market}:${it.code}" }) { security ->
            Column(
                Modifier.fillMaxWidth().clickable { onClick(security) }.padding(vertical = 12.dp)
                    .testTag("security-${security.market}-${security.code}"),
            ) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("${security.code} ${security.name}")
                    Text(if (security.market == MarketCode.TWSE) "上市" else "上櫃")
                }
                Text(security.primaryIndustry ?: "產業資料未提供")
                Text("資料狀態：${security.dataStatus}")
            }
            HorizontalDivider()
        }
    }
}

@Composable
fun SecurityDetailRoute(
    code: String,
    market: MarketCode,
    viewModel: SecurityDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var tab by remember { mutableIntStateOf(0) }
    LaunchedEffect(code, market) { viewModel.load(code, market) }
    Column {
        Row {
            TextButton(onClick = { tab = 0 }) { Text("走勢") }
            TextButton(onClick = { tab = 1 }) { Text("基本資料") }
        }
        if (tab == 0) SecurityChartRoute(code, market) else SecurityDetailScreen(state)
    }
}

@Composable
fun SecurityDetailScreen(state: SecurityDetailUiState) {
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        when (state) {
            SecurityDetailUiState.Loading -> CircularProgressIndicator()
            is SecurityDetailUiState.Error -> StateMessage("載入失敗：${state.message}")
            is SecurityDetailUiState.Offline -> StateMessage(state.message)
            is SecurityDetailUiState.Stale -> { Text("離線快取資料"); SecurityBasicData(state.security) }
            is SecurityDetailUiState.Success -> SecurityBasicData(state.security)
        }
    }
}

@Composable
private fun SecurityBasicData(security: Security) {
    Text("${security.code} ${security.name}", modifier = Modifier.testTag("security-detail-title"))
    Text("市場：${if (security.market == MarketCode.TWSE) "上市" else "上櫃"}")
    Text("證券種類：普通股")
    Text("主要產業：${security.primaryIndustry ?: "未提供"}")
    Text("掛牌日期：${security.listingDate ?: "未提供"}")
    Text("有效狀態：${if (security.isActive) "有效" else "停止顯示"}")
    Text("最後更新：${security.asOf}")
    Text("資料狀態：${security.dataStatus}")
    HorizontalDivider()
    Text("股價、K 線、法人與技術指標尚未在本階段提供")
}

@Composable
fun SecurityChartRoute(
    code: String,
    market: MarketCode,
    viewModel: SecurityChartViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val range by viewModel.range.collectAsStateWithLifecycle()
    val basis by viewModel.basis.collectAsStateWithLifecycle()
    val indicators by viewModel.indicators.collectAsStateWithLifecycle()
    val selected by viewModel.selected.collectAsStateWithLifecycle()
    LaunchedEffect(code, market) { viewModel.load(code, market) }
    SecurityChartScreen(state, range, basis, indicators, selected,
        viewModel::selectRange, viewModel::selectBasis, viewModel::toggleIndicator,
        viewModel::selectCandle)
}

@Composable
fun SecurityChartScreen(
    state: SecurityChartUiState,
    range: ChartRange,
    basis: PriceBasis,
    indicators: Set<String>,
    selected: Candle?,
    onRange: (ChartRange) -> Unit,
    onBasis: (PriceBasis) -> Unit,
    onIndicator: (String) -> Unit,
    onSelect: (Candle?) -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            ChartRange.entries.forEach { item ->
                FilterChip(selected = range == item, onClick = { onRange(item) }, label = { Text(item.label()) })
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PriceBasis.entries.forEach { item ->
                FilterChip(selected = basis == item, onClick = { onBasis(item) }, label = { Text(item.name) })
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            listOf("MA20", "BBANDS_UPPER", "MACD", "RSI14").forEach { name ->
                FilterChip(selected = name in indicators, onClick = { onIndicator(name) }, label = { Text(name) })
            }
        }
        when (state) {
            SecurityChartUiState.Loading -> CircularProgressIndicator(Modifier.testTag("chart-loading"))
            SecurityChartUiState.Empty -> Text("此期間沒有可用日 K 資料")
            is SecurityChartUiState.Error -> StateMessage("走勢載入失敗：${state.message}")
            is SecurityChartUiState.Offline -> StateMessage(state.message)
            is SecurityChartUiState.Content -> {
                Text("${if (basis == PriceBasis.RAW) "實際歷史成交價" else "調整後技術分析價格"} · ${state.status}")
                if (state.stale) Text("Offline / Stale：顯示最後快取，非最新資料")
                if (state.partial) Text("Partial：部分資料缺失")
                state.note?.let { Text(it) }
                CandlestickChart(state.candles, state.technicals, indicators, selected, onSelect)
                selected?.let { Text("${it.time} O ${it.open} H ${it.high} L ${it.low} C ${it.close} V ${it.volumeShares ?: "--"}") }
                val secondary = indicators.filter { it in setOf("MACD", "RSI14", "KD_K", "ATR14", "OBV", "WILLIAMS_R") }.take(2)
                secondary.forEach { name -> IndicatorPanel(name, state.technicals) }
                state.technicals.lastOrNull()?.let { point ->
                    Text(point.indicators.filter { it.name in indicators }.joinToString(" · ") { "${it.name} ${it.value ?: "--"}" })
                }
                Text("最後更新 ${state.asOf}")
            }
        }
    }
}

@Composable
fun CandlestickChart(
    candles: List<Candle>,
    technicals: List<TechnicalPoint> = emptyList(),
    indicators: Set<String> = emptySet(),
    selected: Candle?,
    onSelect: (Candle?) -> Unit,
) {
    var scale by remember { androidx.compose.runtime.mutableFloatStateOf(1f) }
    var offset by remember { androidx.compose.runtime.mutableFloatStateOf(0f) }
    Canvas(
        Modifier.fillMaxWidth().height(280.dp).testTag("candlestick-chart")
            .pointerInput(candles) {
                detectTransformGestures { _, pan, zoom, _ ->
                    scale = (scale * zoom).coerceIn(1f, 8f)
                    offset += pan.x
                }
            }
            .pointerInput(candles, scale, offset) {
                detectTapGestures { tap ->
                    if (candles.isNotEmpty()) {
                        val widthPer = size.width / candles.size * scale
                        val index = ((tap.x - offset) / widthPer).toInt().coerceIn(candles.indices)
                        onSelect(candles[index])
                    }
                }
            },
    ) {
        if (candles.isEmpty()) return@Canvas
        val highs = candles.map { it.high.toFloat() }
        val lows = candles.map { it.low.toFloat() }
        val maximum = highs.max()
        val minimum = lows.min()
        val priceSpan = (maximum - minimum).coerceAtLeast(0.0001f)
        val widthPer = size.width / candles.size * scale
        candles.forEachIndexed { index, candle ->
            val x = offset + index * widthPer + widthPer / 2
            val yHigh = size.height * (maximum - candle.high.toFloat()) / priceSpan
            val yLow = size.height * (maximum - candle.low.toFloat()) / priceSpan
            val yOpen = size.height * (maximum - candle.open.toFloat()) / priceSpan
            val yClose = size.height * (maximum - candle.close.toFloat()) / priceSpan
            val color = if (candle.close.toFloat() >= candle.open.toFloat()) Color.Red else Color(0xFF008000)
            drawLine(color, Offset(x, yHigh), Offset(x, yLow), 2f)
            drawLine(color, Offset(x - widthPer * .3f, yOpen), Offset(x + widthPer * .3f, yOpen), 5f)
            drawLine(color, Offset(x - widthPer * .3f, yClose), Offset(x + widthPer * .3f, yClose), 5f)
            if (selected?.time == candle.time) drawLine(Color.Blue, Offset(x, 0f), Offset(x, size.height), 2f)
        }
        val overlayNames = indicators.filter {
            it.startsWith("MA") || it.startsWith("EMA") || it.startsWith("BBANDS")
        }
        val technicalByDate = technicals.associateBy { it.tradeDate }
        overlayNames.forEachIndexed { lineIndex, name ->
            val path = Path()
            var started = false
            candles.forEachIndexed { index, candle ->
                val date = candle.time.take(10)
                val value = technicalByDate[date]?.indicators?.firstOrNull { it.name == name }
                    ?.value?.toFloatOrNull() ?: return@forEachIndexed
                val x = offset + index * widthPer + widthPer / 2
                val y = size.height * (maximum - value) / priceSpan
                if (!started) { path.moveTo(x, y); started = true } else path.lineTo(x, y)
            }
            if (started) drawPath(path, listOf(Color.Blue, Color.Magenta, Color.Cyan)[lineIndex % 3], style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2f))
        }
    }
}

@Composable
private fun IndicatorPanel(name: String, technicals: List<TechnicalPoint>) {
    val values = technicals.mapNotNull { point ->
        point.indicators.firstOrNull { it.name == name }?.value?.toFloatOrNull()
    }
    Column {
        Text(name)
        Canvas(Modifier.fillMaxWidth().height(90.dp).testTag("indicator-$name")) {
            if (values.size < 2) return@Canvas
            val high = values.max()
            val low = values.min()
            val span = (high - low).coerceAtLeast(.0001f)
            val path = Path()
            values.forEachIndexed { index, value ->
                val x = size.width * index / (values.size - 1)
                val y = size.height * (high - value) / span
                if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
            }
            drawPath(path, Color.Blue, style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2f))
        }
    }
}

private fun ChartRange.label() = when (this) {
    ChartRange.ONE_DAY -> "1D"
    ChartRange.FIVE_DAYS -> "5D"
    ChartRange.TEN_DAYS -> "10D"
    ChartRange.THIRTY_DAYS -> "30D"
    ChartRange.ONE_YEAR -> "1Y"
    ChartRange.FIVE_YEARS -> "5Y"
}
