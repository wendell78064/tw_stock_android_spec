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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
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
import tw.market.ledger.model.*

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
    onAlert: (String?) -> Unit = {},
    viewModel: SecurityDetailViewModel = hiltViewModel(),
    spotViewModel: SecuritySpotViewModel = hiltViewModel(),
    aiPromptViewModel: SecurityAiPromptViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var tab by remember { mutableIntStateOf(0) }
    LaunchedEffect(code, market) { viewModel.load(code, market) }
    LaunchedEffect(code, market) { spotViewModel.load(code, market) }
    LaunchedEffect(code, market) { aiPromptViewModel.load(code, market) }
    val institutional by spotViewModel.institutional.collectAsStateWithLifecycle()
    val credit by spotViewModel.credit.collectAsStateWithLifecycle()
    val window by spotViewModel.window.collectAsStateWithLifecycle()
    val aiPromptState by aiPromptViewModel.uiState.collectAsStateWithLifecycle()
    Column {
        Row {
            TextButton(onClick = { tab = 0 }, modifier = Modifier.testTag("tab-chart")) { Text("走勢") }
            TextButton(onClick = { tab = 1 }, modifier = Modifier.testTag("tab-spot")) { Text("籌碼") }
            TextButton(onClick = { tab = 2 }, modifier = Modifier.testTag("tab-credit")) { Text("信用") }
            TextButton(onClick = { tab = 3 }, modifier = Modifier.testTag("tab-basic")) { Text("基本資料") }
            TextButton(onClick = { tab = 4 }, modifier = Modifier.testTag("tab-ai-analysis")) { Text("AI 分析") }
            TextButton(onClick = { onAlert((state as? SecurityDetailUiState.Success)?.security?.id) }) { Text("提醒") }
        }
        when (tab) {
            0 -> SecurityChartRoute(code, market)
            1 -> SecurityInstitutionalScreen(institutional, window, spotViewModel::loadInstitutional)
            2 -> SecurityCreditScreen(credit)
            3 -> SecurityDetailScreen(state)
            4 -> SecurityAiPromptScreen(aiPromptState, onRetry = { aiPromptViewModel.load(code, market) })
            else -> SecurityDetailScreen(state)
        }
    }
}

@Composable
fun SecurityAiPromptScreen(
    state: SecurityAiPromptUiState,
    onRetry: () -> Unit = {},
) {
    val clipboardManager = androidx.compose.ui.platform.LocalClipboardManager.current
    var copied by remember { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxSize()
            .padding(16.dp)
            .testTag("security-ai-prompt-screen"),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        when (state) {
            SecurityAiPromptUiState.Idle -> Text("點擊載入 AI 分析 Prompt")
            SecurityAiPromptUiState.Loading -> CircularProgressIndicator(Modifier.testTag("ai-prompt-loading"))
            is SecurityAiPromptUiState.Error -> {
                Text("載入 AI Prompt 失敗：${state.message}")
                Button(onClick = onRetry) { Text("重試") }
            }
            is SecurityAiPromptUiState.Success -> {
                val prompt = state.prompt
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            "${prompt.security.code} ${prompt.security.name} AI 分析 Prompt",
                            style = androidx.compose.material3.MaterialTheme.typography.titleMedium,
                            modifier = Modifier.testTag("security-ai-prompt-title")
                        )
                        Text(
                            "基準：${prompt.asOf} · 狀態：${prompt.dataStatus} · 字數：${prompt.characterCount}",
                            style = androidx.compose.material3.MaterialTheme.typography.bodySmall
                        )
                    }
                    Button(
                        onClick = {
                            clipboardManager.setText(androidx.compose.ui.text.AnnotatedString(prompt.prompt))
                            copied = true
                        },
                        modifier = Modifier.testTag("security-ai-prompt-copy-btn")
                    ) {
                        Text(if (copied) "已複製！" else "複製 Prompt")
                    }
                }
                if (copied) {
                    Text(
                        "✓ 已成功複製到剪貼簿，可直接貼至 ChatGPT / Gemini / Claude 進行深度分析！",
                        color = Color(0xFF2E7D32),
                        style = androidx.compose.material3.MaterialTheme.typography.bodySmall,
                        modifier = Modifier.testTag("security-ai-prompt-copied-banner")
                    )
                }
                HorizontalDivider()
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag("security-ai-prompt-content")
                ) {
                    item {
                        Text(
                            text = prompt.prompt,
                            style = androidx.compose.material3.MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }
                }
            }
        }
    }
}


@Composable fun SecurityInstitutionalScreen(state: SecuritySpotUiState, window: Int, onWindow: (Int) -> Unit) {
    Column(Modifier.fillMaxSize().padding(12.dp).testTag("security-institutional"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row { listOf(1,5,10,20,60).forEach { FilterChip(selected = window == it, onClick = { onWindow(it) }, label = { Text("$it") }) } }
        when (state) { SecuritySpotUiState.Loading -> CircularProgressIndicator(); SecuritySpotUiState.Empty -> Text("此期間沒有法人資料")
            is SecuritySpotUiState.Error -> Text("籌碼載入失敗：${state.message}"); is SecuritySpotUiState.Offline -> Text("Offline / Stale：${state.message}")
            is SecuritySpotUiState.Institutional -> { state.points.takeLast(12).forEach { Text("${it.tradeDate} ${it.institutionType} ${it.dealerSubtype ?: ""} 淨 ${it.net ?: "--"} 累計 ${it.cumulativeNet ?: "--"}") }
                state.points.lastOrNull()?.let { Text("連續方向 ${it.consecutiveDirectionDays} 個交易日 · ${it.dataStatus}") } }
            is SecuritySpotUiState.Credit -> Text("資料型態錯誤") }
    }
}

@Composable fun SecurityCreditScreen(state: SecuritySpotUiState) {
    Column(Modifier.fillMaxSize().padding(12.dp).testTag("security-credit"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        when (state) { SecuritySpotUiState.Loading -> CircularProgressIndicator(); SecuritySpotUiState.Empty -> Text("目前沒有信用交易資料")
            is SecuritySpotUiState.Error -> Text("信用載入失敗：${state.message}"); is SecuritySpotUiState.Offline -> Text("Offline / Stale：${state.message}")
            is SecuritySpotUiState.Credit -> { Text("融資", style = androidx.compose.material3.MaterialTheme.typography.titleMedium); state.credit.margins.lastOrNull()?.let { Text("餘額 ${it.marginBalance ?: "--"} 今日增減 ${it.marginBalanceChange ?: "--"}") }
                Text("融券", style = androidx.compose.material3.MaterialTheme.typography.titleMedium); state.credit.margins.lastOrNull()?.let { Text("餘額 ${it.shortBalance ?: "--"} 今日增減 ${it.shortBalanceChange ?: "--"} 券資比 ${it.shortMarginRatio ?: "--"}") }
                Text("借券", style = androidx.compose.material3.MaterialTheme.typography.titleMedium); state.credit.lending.lastOrNull()?.let { Text("賣出 ${it.lendingSell ?: "--"} 餘額 ${it.lendingBalance ?: "--"} 今日增減 ${it.lendingBalanceChange ?: "--"}") } }
            is SecuritySpotUiState.Institutional -> Text("資料型態錯誤") }
    }
}

@Composable
fun SecurityDetailScreen(state: SecurityDetailUiState, realtimeQuote: RealtimeQuote? = null) {
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        realtimeQuote?.let { q ->
            Row(
                modifier = Modifier.fillMaxWidth().testTag("realtime-quote-badge"),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("即時價格: $${q.lastPrice} (${q.changePercent ?: "0"}%)", modifier = Modifier.testTag("realtime-last-price"))
                Text("[${q.dataStatus.name}]", color = if (q.dataStatus == RealtimeDataStatus.LIVE) Color.Red else Color.Gray, modifier = Modifier.testTag("realtime-status-badge"))
            }
            HorizontalDivider()
        }
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
    Text("主要產業：${security.primaryIndustry ?: "未提供"}", modifier = Modifier.testTag("security-detail-industry"))
    if (security.themes.isNotEmpty()) {
        Text("所屬題材：${security.themes.joinToString(", ") { it.name }}", modifier = Modifier.testTag("security-detail-themes"))
    } else {
        Text("所屬題材：無", modifier = Modifier.testTag("security-detail-themes"))
    }
    Text("掛牌日期：${security.listingDate ?: "未提供"}")
    Text("資料時間：${security.asOf}")
    Text("資料狀態：${security.dataStatus}")
}

@Composable
fun SecurityChartRoute(
    code: String,
    market: MarketCode,
    viewModel: SecurityChartViewModel = hiltViewModel(),
    intradayViewModel: IntradayChartViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val range by viewModel.range.collectAsStateWithLifecycle()
    val basis by viewModel.basis.collectAsStateWithLifecycle()
    val indicators by viewModel.indicators.collectAsStateWithLifecycle()
    val selected by viewModel.selected.collectAsStateWithLifecycle()
    val preferences by viewModel.preferences.collectAsStateWithLifecycle()
    val settingsState by viewModel.settingsUiState.collectAsStateWithLifecycle()
    val intradayState by intradayViewModel.state.collectAsStateWithLifecycle()
    var settingsOpen by remember { mutableStateOf(false) }
    LaunchedEffect(code, market) { viewModel.load(code, market) }
    LaunchedEffect(code, market, range) {
        if (range == ChartRange.ONE_DAY) intradayViewModel.load(code, market)
    }
    if (range == ChartRange.ONE_DAY) {
        Column {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                ChartRange.entries.forEach { item ->
                    FilterChip(selected = range == item, onClick = { viewModel.selectRange(item) }, label = { Text(item.label()) })
                }
            }
            IntradayChartScreen(intradayState, intradayViewModel::selectInterval, intradayViewModel::setFollowLatest)
        }
        return
    }
    SecurityChartScreen(state, range, basis, indicators, selected,
        viewModel::selectRange, viewModel::selectBasis, viewModel::toggleIndicator,
        viewModel::selectCandle, onSettings = { settingsOpen = true })
    if (settingsOpen) IndicatorSettingsDialog(preferences, settingsState,
        onDismiss = { settingsOpen = false }, onSave = viewModel::savePreferences,
        onResetAll = viewModel::resetAllPreferences)
}

@Composable
fun IntradayChartScreen(
    state: IntradayUiState,
    onInterval: (IntradayInterval) -> Unit,
    onFollowLatest: (Boolean) -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(12.dp).testTag("intraday-1d-chart"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        when (state) {
            IntradayUiState.Loading -> CircularProgressIndicator(Modifier.testTag("intraday-loading"))
            is IntradayUiState.Error -> Text("盤中走勢載入失敗：${state.message}")
            IntradayUiState.Unavailable -> Text("即時盤中行情尚未配置", modifier = Modifier.testTag("intraday-unavailable"))
            is IntradayUiState.Content -> {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IntradayInterval.entries.forEach { interval ->
                        FilterChip(
                            selected = state.chart.interval == interval,
                            onClick = { onInterval(interval) },
                            label = { Text(interval.apiValue) },
                            modifier = Modifier.testTag("intraday-${interval.apiValue}"),
                        )
                    }
                }
                val status = when (state.chart.connection) {
                    RealtimeConnectionState.CONNECTED -> if (state.chart.partial) "Stale" else "LIVE"
                    RealtimeConnectionState.RECONNECTING -> "Reconnecting"
                    RealtimeConnectionState.UNAVAILABLE -> "Unavailable"
                    else -> state.chart.connection.name
                }
                Text(status, modifier = Modifier.testTag("intraday-connection-state"))
                if (state.chart.candles.isEmpty()) Text("目前沒有盤中成交") else {
                    var selected by remember(state.chart.interval) { mutableStateOf<IntradayCandle?>(null) }
                    val candles = state.chart.candles.map {
                        Candle(it.bucketStart, it.open, it.high, it.low, it.close, it.volume, it.turnoverAmount)
                    }
                    CandlestickChart(candles, emptyList(), emptySet(), selected?.let {
                        Candle(it.bucketStart, it.open, it.high, it.low, it.close, it.volume, it.turnoverAmount)
                    }) { chosen -> selected = chosen?.let { c -> state.chart.candles.firstOrNull { it.bucketStart == c.time } } }
                    selected?.let { Text("${it.bucketStart} O ${it.open} H ${it.high} L ${it.low} C ${it.close} V ${it.volume}", modifier = Modifier.testTag("intraday-ohlcv")) }
                    Text("成交量 ${state.chart.candles.last().volume}", modifier = Modifier.testTag("intraday-volume"))
                }
                TextButton(onClick = { onFollowLatest(!state.chart.followLatest) }) {
                    Text(if (state.chart.followLatest) "跟隨最新" else "查看歷史")
                }
                Text("最後更新 ${state.chart.asOf ?: "--"}")
            }
        }
    }
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
    onSettings: () -> Unit = {},
) {
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            ChartRange.entries.forEach { item ->
                FilterChip(selected = range == item, onClick = { onRange(item) }, label = { Text(item.label()) })
            }
        }
        Button(onClick = onSettings, modifier = Modifier.testTag("indicator-settings")) { Text("指標設定") }
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
            SecurityChartUiState.Empty -> Text(if (basis == PriceBasis.ADJUSTED) "官方來源未提供還原價資料，請切換至 RAW 檢視實際成交價" else "此期間沒有可用日 K 資料")
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
fun IndicatorSettingsDialog(
    current: TechnicalIndicatorPreferences,
    state: IndicatorSettingsUiState,
    onDismiss: () -> Unit,
    onSave: (TechnicalIndicatorPreferences) -> Unit,
    onResetAll: () -> Unit,
) {
    var draft by remember(current) { mutableStateOf(current) }
    var editing by remember { mutableStateOf<String?>(null) }
    val error = (state as? IndicatorSettingsUiState.ValidationError)?.message
    AlertDialog(
        modifier = Modifier.testTag("indicator-settings-dialog"), onDismissRequest = onDismiss,
        title = { Text(if (editing == null) "技術指標參數" else editing!!) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (editing == null) {
                    listOf(
                        "MA" to draft.ma.periods.joinToString(" / "), "EMA" to draft.ema.periods.joinToString(" / "),
                        "Bollinger" to "${draft.bollinger.period} / ${draft.bollinger.standardDeviationMultiplier}",
                        "MACD" to "${draft.macd.fast} / ${draft.macd.slow} / ${draft.macd.signal}",
                        "RSI" to draft.rsi.period.toString(), "KD" to "${draft.kd.rsvPeriod} / ${draft.kd.kSmoothing} / ${draft.kd.dSmoothing}",
                        "ATR" to draft.atr.period.toString(), "OBV" to "無數值參數",
                        "Williams %R" to draft.williamsR.period.toString(),
                    ).forEach { (name, value) ->
                        Row(Modifier.fillMaxWidth().clickable { if (name != "OBV") editing = name }
                            .padding(8.dp).testTag("setting-$name"), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(name); Text(value)
                        }
                    }
                    error?.let { Text(it, color = Color.Red, modifier = Modifier.testTag("settings-validation-error")) }
                    TextButton(onClick = { draft = TechnicalIndicatorPreferences.Default; onResetAll() }) { Text("全部重設預設值") }
                } else {
                    IndicatorEditor(editing!!, draft) { draft = it }
                    TextButton(onClick = {
                        draft = when (editing) {
                            "MA" -> draft.copy(ma = MaSettings()); "EMA" -> draft.copy(ema = EmaSettings())
                            "Bollinger" -> draft.copy(bollinger = BollingerSettings()); "MACD" -> draft.copy(macd = MacdSettings())
                            "RSI" -> draft.copy(rsi = RsiSettings()); "KD" -> draft.copy(kd = KdSettings())
                            "ATR" -> draft.copy(atr = AtrSettings()); else -> draft.copy(williamsR = WilliamsRSettings())
                        }
                    }) { Text("重設此指標") }
                    error?.let { Text(it, color = Color.Red, modifier = Modifier.testTag("settings-validation-error")) }
                }
            }
        },
        confirmButton = { TextButton(onClick = { if (editing == null) onSave(draft) else editing = null },
            modifier = Modifier.testTag("settings-save")) { Text(if (editing == null) "儲存" else "完成") } },
        dismissButton = { TextButton(onClick = { if (editing == null) onDismiss() else editing = null }) { Text("取消") } },
    )
}

@Composable
private fun IndicatorEditor(name: String, value: TechnicalIndicatorPreferences,
                            update: (TechnicalIndicatorPreferences) -> Unit) {
    @Composable fun Field(label: String, text: String, change: (String) -> Unit) = OutlinedTextField(
        value = text, onValueChange = change, label = { Text(label) }, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Number),
        modifier = Modifier.fillMaxWidth().testTag("parameter-$label"))
    when (name) {
        "MA" -> Field("MA periods", value.ma.periods.joinToString(",")) { raw -> update(value.copy(ma = MaSettings(raw.split(",").mapNotNull { it.trim().toIntOrNull() }))) }
        "EMA" -> Field("EMA periods", value.ema.periods.joinToString(",")) { raw -> update(value.copy(ema = EmaSettings(raw.split(",").mapNotNull { it.trim().toIntOrNull() }))) }
        "RSI" -> Field("RSI period", value.rsi.period.toString()) { update(value.copy(rsi = RsiSettings(it.toIntOrNull() ?: 0))) }
        "ATR" -> Field("ATR period", value.atr.period.toString()) { update(value.copy(atr = AtrSettings(it.toIntOrNull() ?: 0))) }
        "Williams %R" -> Field("Williams period", value.williamsR.period.toString()) { update(value.copy(williamsR = WilliamsRSettings(it.toIntOrNull() ?: 0))) }
        "Bollinger" -> { Field("Bollinger period", value.bollinger.period.toString()) { update(value.copy(bollinger = value.bollinger.copy(period = it.toIntOrNull() ?: 0))) }; Field("Stddev multiplier", value.bollinger.standardDeviationMultiplier) { update(value.copy(bollinger = value.bollinger.copy(standardDeviationMultiplier = it))) } }
        "MACD" -> { Field("MACD fast", value.macd.fast.toString()) { update(value.copy(macd = value.macd.copy(fast = it.toIntOrNull() ?: 0))) }; Field("MACD slow", value.macd.slow.toString()) { update(value.copy(macd = value.macd.copy(slow = it.toIntOrNull() ?: 0))) }; Field("MACD signal", value.macd.signal.toString()) { update(value.copy(macd = value.macd.copy(signal = it.toIntOrNull() ?: 0))) } }
        "KD" -> { Field("RSV period", value.kd.rsvPeriod.toString()) { update(value.copy(kd = value.kd.copy(rsvPeriod = it.toIntOrNull() ?: 0))) }; Field("K smoothing", value.kd.kSmoothing.toString()) { update(value.copy(kd = value.kd.copy(kSmoothing = it.toIntOrNull() ?: 0))) }; Field("D smoothing", value.kd.dSmoothing.toString()) { update(value.copy(kd = value.kd.copy(dSmoothing = it.toIntOrNull() ?: 0))) } }
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
