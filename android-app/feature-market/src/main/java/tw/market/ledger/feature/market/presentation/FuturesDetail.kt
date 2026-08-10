package tw.market.ledger.feature.market.presentation

import androidx.compose.foundation.layout.*
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
import javax.inject.Inject
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.market.domain.DerivativesRepository
import tw.market.ledger.model.*

sealed interface FuturesDetailUiState {
    data object Loading : FuturesDetailUiState
    data class Loaded(val overview: FuturesOverview, val positions: List<FuturesInstitutionalPosition>,
        val candles: List<ContinuousFuturesPoint>, val stale: Boolean = false) : FuturesDetailUiState
    data class Error(val message: String) : FuturesDetailUiState
}

@HiltViewModel class FuturesDetailViewModel @Inject constructor(
    private val repository: DerivativesRepository) : ViewModel() {
    private val _state = MutableStateFlow<FuturesDetailUiState>(FuturesDetailUiState.Loading)
    val state = _state.asStateFlow()
    val range = MutableStateFlow(FuturesRange.D30)
    val rollMethod = MutableStateFlow(RollMethod.OPEN_INTEREST)
    fun load(product: String) = viewModelScope.launch {
        _state.value = FuturesDetailUiState.Loading
        try {
            val overview = async { repository.overview(product) }
            val positions = async { repository.positions(product, 20) }
            val candles = async { repository.continuous(product, range.value, rollMethod.value) }
            val value = overview.await()
            _state.value = FuturesDetailUiState.Loaded(value, positions.await(), candles.await(), value.fromCache)
        } catch (error: IOException) { _state.value = FuturesDetailUiState.Error("離線且沒有期貨快取") }
        catch (error: Exception) { _state.value = FuturesDetailUiState.Error(error.message ?: "期貨資料載入失敗") }
    }
    fun selectRange(product: String, value: FuturesRange) { range.value = value; load(product) }
    fun selectRoll(product: String, value: RollMethod) { rollMethod.value = value; load(product) }
}

@Composable fun FuturesDetailRoute(product: String, viewModel: FuturesDetailViewModel = hiltViewModel()) {
    LaunchedEffect(product) { viewModel.load(product) }
    val state by viewModel.state.collectAsStateWithLifecycle()
    val range by viewModel.range.collectAsStateWithLifecycle()
    val roll by viewModel.rollMethod.collectAsStateWithLifecycle()
    FuturesDetailScreen(product, state, range, roll, { viewModel.selectRange(product, it) },
        { viewModel.selectRoll(product, it) })
}

@Composable fun FuturesDetailScreen(product: String, state: FuturesDetailUiState, range: FuturesRange,
    roll: RollMethod, onRange: (FuturesRange) -> Unit, onRoll: (RollMethod) -> Unit) {
    when (state) {
        FuturesDetailUiState.Loading -> CircularProgressIndicator(Modifier.testTag("futures-loading"))
        is FuturesDetailUiState.Error -> Text(state.message, Modifier.testTag("futures-error"))
        is FuturesDetailUiState.Loaded -> Column(Modifier.fillMaxSize().padding(12.dp).testTag("futures-detail"),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("$product ${state.overview.product.name}", style = MaterialTheme.typography.headlineSmall)
            if (state.stale) Text("Offline / Stale：顯示最後快取，不冒充最新資料")
            state.overview.near?.let { Text("近月 ${it.contractCode} 收 ${it.close ?: "--"} OI ${it.openInterest ?: "--"} 基差 ${it.closeBasis ?: "--"}") }
            state.overview.next?.let { Text("次月 ${it.contractCode} 收 ${it.close ?: "--"} OI ${it.openInterest ?: "--"}") }
            Row { FuturesRange.entries.forEach { FilterChip(range == it, { onRange(it) }, { Text(it.name) }) } }
            Row { RollMethod.entries.forEach { FilterChip(roll == it, { onRoll(it) }, { Text(it.name) }) } }
            Text("連續期貨（不回補調整） ${state.candles.size} 點")
            Text("法人未平倉", style = MaterialTheme.typography.titleMedium)
            state.positions.takeLast(4).forEach { Text("${it.institutionType} 淨OI ${it.netOi ?: "--"} 日變化 ${it.netOiChange ?: "--"}") }
            Text("選擇權 Put/Call、履約價 OI、Max Pain 與 VIX 由市場風險卡呈現；缺資料明示 unavailable。")
        }
    }
}
