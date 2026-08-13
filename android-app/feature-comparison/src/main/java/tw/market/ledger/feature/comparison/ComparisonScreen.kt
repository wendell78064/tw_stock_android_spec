package tw.market.ledger.feature.comparison

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.network.ComparisonApi
import tw.market.ledger.network.RunComparisonInputDto
import tw.market.ledger.network.SecurityTargetInputDto

data class SecurityTarget(val code: str_Code, val market: MarketCode)
typealias str_Code = String

data class ObjectiveSignal(
    val signalType: String,
    val subjectCode: String,
    val comparatorCode: String,
    val headline: String,
    val details: String
)

data class NormalizedPoint(val date: String, val values: Map<String, Float?>)

data class ComparisonSecuritySummary(
    val code: String,
    val name: String,
    val close: String?,
    val return20d: String?,
    val rsi14: String?,
    val foreign1dNet: String?,
    val dataStatus: DataStatus
)

data class ComparisonUiState(
    val selectedTargets: List<SecurityTarget> = emptyList(),
    val window: String = "20D",
    val isLoading: Boolean = false,
    val summaries: List<ComparisonSecuritySummary> = emptyList(),
    val normalizedSeries: List<NormalizedPoint> = emptyList(),
    val signals: List<ObjectiveSignal> = emptyList(),
    val errorMessage: String? = null,
    val dataStatus: DataStatus = DataStatus.FINAL
)

class ComparisonSelectionManager {
    private val _targets = MutableStateFlow<List<SecurityTarget>>(emptyList())
    val targets: StateFlow<List<SecurityTarget>> = _targets.asStateFlow()

    fun addTarget(target: SecurityTarget): Boolean {
        if (_targets.value.size >= 5) return false
        if (_targets.value.any { it.code == target.code && it.market == target.market }) return false
        _targets.value = _targets.value + target
        return true
    }

    fun removeTarget(code: String, market: MarketCode) {
        _targets.value = _targets.value.filterNot { it.code == code && it.market == market }
    }

    fun clear() {
        _targets.value = emptyList()
    }
}

@HiltViewModel
class ComparisonViewModel @Inject constructor(
    private val api: ComparisonApi
) : ViewModel() {
    private val _uiState = MutableStateFlow(ComparisonUiState())
    val uiState: StateFlow<ComparisonUiState> = _uiState.asStateFlow()

    fun setTargets(targets: List<SecurityTarget>) {
        _uiState.value = _uiState.value.copy(selectedTargets = targets)
        if (targets.size >= 2) {
            runComparison()
        }
    }

    fun setWindow(win: String) {
        _uiState.value = _uiState.value.copy(window = win)
        if (_uiState.value.selectedTargets.size >= 2) {
            runComparison()
        }
    }

    fun runComparison() {
        val targets = _uiState.value.selectedTargets
        if (targets.size < 2) {
            _uiState.value = _uiState.value.copy(errorMessage = "Comparison requires at least 2 securities")
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            try {
                val input = RunComparisonInputDto(
                    targets = targets.map { SecurityTargetInputDto(it.code, it.market.name) },
                    window = _uiState.value.window
                )
                val res = api.runComparison(input)
                if (res.isSuccessful && res.body() != null) {
                    val body = res.body()!!.data
                    val summaries = body.securities.map {
                        ComparisonSecuritySummary(
                            code = it.code,
                            name = it.name,
                            close = it.latest_close,
                            return20d = it.return_20d,
                            rsi14 = it.rsi14,
                            foreign1dNet = it.foreign_1d_net,
                            dataStatus = DataStatus.valueOf(it.data_status)
                        )
                    }
                    val series = body.normalized_series.map { p ->
                        NormalizedPoint(
                            date = p.trade_date,
                            values = p.values.mapValues { it.value?.toFloatOrNull() }
                        )
                    }
                    val signals = body.objective_signals.map {
                        ObjectiveSignal(
                            signalType = it.signal_type,
                            subjectCode = it.subject_code,
                            comparatorCode = it.comparator_code,
                            headline = it.headline,
                            details = it.details
                        )
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        summaries = summaries,
                        normalizedSeries = series,
                        signals = signals,
                        dataStatus = DataStatus.valueOf(res.body()!!.meta.dataStatus)
                    )
                } else {
                    _uiState.value = _uiState.value.copy(isLoading = false, errorMessage = "Failed to run comparison")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, errorMessage = e.message)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ComparisonScreen(
    viewModel: ComparisonViewModel,
    onNavigateBack: () -> Unit
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("個股比較 (${state.selectedTargets.size}/5)") }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .testTag("comparison_screen")
        ) {
            if (state.selectedTargets.size < 2) {
                Text(
                    "請至少選擇 2 檔股票進行比較 (最多 5 檔)",
                    modifier = Modifier.testTag("txt_min_selection_warning")
                )
            } else if (state.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.CenterHorizontally).testTag("loading_indicator"))
            } else {
                // Window Switcher
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)
                ) {
                    listOf("1D", "5D", "10D", "20D", "60D", "1Y").forEach { win ->
                        FilterChip(
                            selected = state.window == win,
                            onClick = { viewModel.setWindow(win) },
                            label = { Text(win) },
                            modifier = Modifier.testTag("chip_window_$win")
                        )
                    }
                }

                LazyColumn(modifier = Modifier.fillMaxSize()) {
                    item {
                        Text("走勢基期比較 (Base=100)", style = MaterialTheme.typography.titleMedium)
                        NormalizedCanvasChart(series = state.normalizedSeries)
                        Spacer(modifier = Modifier.height(16.dp))
                    }

                    item {
                        Text("指標比較表", style = MaterialTheme.typography.titleMedium)
                        Spacer(modifier = Modifier.height(8.dp))
                    }

                    items(state.summaries) { sec ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp)
                                .testTag("sec_summary_${sec.code}")
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(12.dp),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Column {
                                    Text("${sec.name} (${sec.code})", style = MaterialTheme.typography.titleSmall, modifier = Modifier.testTag("code_${sec.code}"))
                                    Text("收盤價: ${sec.close ?: "-"}")
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text("20D報酬: ${sec.return20d ?: "-"}%")
                                    Text("RSI(14): ${sec.rsi14 ?: "-"}")
                                }
                            }
                        }
                    }

                    item {
                        Spacer(modifier = Modifier.height(16.dp))
                        Text("客觀指標背離訊號", style = MaterialTheme.typography.titleMedium)
                        Spacer(modifier = Modifier.height(8.dp))
                    }

                    items(state.signals) { sig ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp)
                                .testTag("signal_${sig.subjectCode}_${sig.comparatorCode}")
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(sig.headline, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.primary)
                                Text(sig.details, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun NormalizedCanvasChart(series: List<NormalizedPoint>) {
    val colors = listOf(Color.Red, Color.Blue, Color.Green, Color.Magenta, Color.Cyan)
    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(180.dp)
            .padding(8.dp)
            .testTag("normalized_canvas_chart")
    ) {
        if (series.isEmpty()) return@Canvas
        val width = size.width
        val height = size.height

        val codes = series.firstOrNull()?.values?.keys?.toList() ?: return@Canvas
        val stepX = if (series.size > 1) width / (series.size - 1) else width

        codes.forEachIndexed { codeIdx, code ->
            val color = colors[codeIdx % colors.size]
            var lastPoint: Offset? = null
            series.forEachIndexed { i, p ->
                val valY = p.values[code] ?: 100f
                val x = i * stepX
                val y = height - ((valY - 80f) / 40f * height).coerceIn(0f, height)
                val currentPoint = Offset(x, y)
                if (lastPoint != null) {
                    drawLine(color = color, start = lastPoint!!, end = currentPoint, strokeWidth = 3f)
                }
                lastPoint = currentPoint
            }
        }
    }
}
