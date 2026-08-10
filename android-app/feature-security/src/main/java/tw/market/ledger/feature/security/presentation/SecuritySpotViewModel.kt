package tw.market.ledger.feature.security.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.market.domain.MarketRepository
import tw.market.ledger.model.*

sealed interface SecuritySpotUiState {
    data object Loading : SecuritySpotUiState
    data object Empty : SecuritySpotUiState
    data class Error(val message: String) : SecuritySpotUiState
    data class Offline(val message: String) : SecuritySpotUiState
    data class Institutional(val points: List<InstitutionalPoint>, val stale: Boolean = false) : SecuritySpotUiState
    data class Credit(val credit: SecurityCredit, val stale: Boolean = false) : SecuritySpotUiState
}
@HiltViewModel class SecuritySpotViewModel @Inject constructor(private val repository: MarketRepository): ViewModel() {
    private val _institutional = MutableStateFlow<SecuritySpotUiState>(SecuritySpotUiState.Loading)
    val institutional: StateFlow<SecuritySpotUiState> = _institutional.asStateFlow()
    private val _credit = MutableStateFlow<SecuritySpotUiState>(SecuritySpotUiState.Loading)
    val credit: StateFlow<SecuritySpotUiState> = _credit.asStateFlow()
    val window = MutableStateFlow(20); private var target: Pair<String, MarketCode>? = null
    fun load(code: String, market: MarketCode) { target = code to market; loadInstitutional(20); loadCredit() }
    fun loadInstitutional(value: Int) { val (code, market) = target ?: return; window.value = value
        viewModelScope.launch { _institutional.value = SecuritySpotUiState.Loading
            try { val rows = repository.securityInstitutional(code, market, value); _institutional.value =
                if (rows.isEmpty()) SecuritySpotUiState.Empty else SecuritySpotUiState.Institutional(rows) }
            catch (_: IOException) { _institutional.value = SecuritySpotUiState.Offline("目前離線且沒有此期間籌碼快取") }
            catch (e: Exception) { _institutional.value = SecuritySpotUiState.Error(e.message ?: "籌碼載入失敗") } } }
    fun loadCredit() { val (code, market) = target ?: return; viewModelScope.launch {
        _credit.value = SecuritySpotUiState.Loading
        try { val result = repository.securityCredit(code, market); _credit.value = if (result.margins.isEmpty() && result.lending.isEmpty()) SecuritySpotUiState.Empty else SecuritySpotUiState.Credit(result) }
        catch (_: IOException) { _credit.value = SecuritySpotUiState.Offline("目前離線且沒有信用交易快取") }
        catch (e: Exception) { _credit.value = SecuritySpotUiState.Error(e.message ?: "信用交易載入失敗") } } }
}
