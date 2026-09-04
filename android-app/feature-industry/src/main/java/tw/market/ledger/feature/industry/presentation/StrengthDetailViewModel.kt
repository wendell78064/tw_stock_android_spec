package tw.market.ledger.feature.industry.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.industry.domain.IndustryRepository
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeQuote
import tw.market.ledger.model.TaxonomyLeader
import tw.market.ledger.model.TaxonomyStrength
import tw.market.ledger.model.TaxonomyStrengthDetail
import tw.market.ledger.network.RealtimeSecurityTarget
import tw.market.ledger.network.RealtimeSubscriptionManager
import javax.inject.Inject

sealed interface StrengthDetailUiState {
    data object Loading : StrengthDetailUiState
    data class Error(val message: String) : StrengthDetailUiState
    data class Success(
        val detail: TaxonomyStrengthDetail,
        val history: List<TaxonomyStrength>,
        val window: Int,
        val isStale: Boolean = false,
    ) : StrengthDetailUiState
}

@HiltViewModel
class StrengthDetailViewModel @Inject constructor(
    private val repository: IndustryRepository,
    private val realtimeSubscriptions: RealtimeSubscriptionManager,
) : ViewModel() {

    private val _uiState = MutableStateFlow<StrengthDetailUiState>(StrengthDetailUiState.Loading)
    val uiState: StateFlow<StrengthDetailUiState> = _uiState.asStateFlow()

    private var currentId: String? = null
    private var isIndustry: Boolean = true
    private var currentWindow: Int = 20
    private var realtimeActive = false

    init {
        viewModelScope.launch {
            realtimeSubscriptions.latestQuotes.collect { quotes ->
                val current = _uiState.value
                if (current is StrengthDetailUiState.Success) {
                    _uiState.value = current.withRealtimeQuotes(quotes)
                }
            }
        }
    }

    fun load(id: String, isIndustryTaxonomy: Boolean, window: Int = 20) {
        currentId = id
        isIndustry = isIndustryTaxonomy
        currentWindow = window

        viewModelScope.launch {
            _uiState.value = StrengthDetailUiState.Loading
            val detailRes = repository.getTaxonomyStrengthDetail(id, isIndustryTaxonomy, window)
            val historyRes = repository.getTaxonomyStrengthHistory(id, isIndustryTaxonomy, window, limit = 60)

            if (detailRes.isSuccess) {
                val detail = detailRes.getOrThrow()
                val history = historyRes.getOrNull()?.first ?: emptyList()
                val historyStale = historyRes.getOrNull()?.second ?: false

                if (realtimeActive) {
                    val targets = (detail.leaders + detail.laggards).mapTo(mutableSetOf()) {
                        RealtimeSecurityTarget(it.market.name, it.code)
                    }
                    realtimeSubscriptions.updateIndustryMembership(targets)
                }

                val successState = StrengthDetailUiState.Success(
                    detail = detail,
                    history = history,
                    window = window,
                    isStale = detail.isStale || historyStale,
                )
                _uiState.value = successState.withRealtimeQuotes(realtimeSubscriptions.latestQuotes.value)
            } else {
                val error = detailRes.exceptionOrNull()?.message ?: "無法載入產業強弱明細"
                _uiState.value = StrengthDetailUiState.Error(error)
            }
        }
    }

    fun setWindow(window: Int) {
        val id = currentId ?: return
        load(id, isIndustry, window)
    }

    fun activateRealtime() {
        realtimeActive = true
        val current = _uiState.value
        if (current is StrengthDetailUiState.Success) {
            val targets = (current.detail.leaders + current.detail.laggards).mapTo(mutableSetOf()) {
                RealtimeSecurityTarget(it.market.name, it.code)
            }
            realtimeSubscriptions.updateIndustryMembership(targets)
        }
    }

    fun deactivateRealtime() {
        realtimeActive = false
        realtimeSubscriptions.releaseIndustryMembership()
    }

    override fun onCleared() {
        deactivateRealtime()
        super.onCleared()
    }

    private fun StrengthDetailUiState.Success.withRealtimeQuotes(quotes: Map<String, RealtimeQuote>): StrengthDetailUiState.Success {
        val updatedLeaders = detail.leaders.map { it.withRealtimeQuote(quotes) }
        val updatedLaggards = detail.laggards.map { it.withRealtimeQuote(quotes) }
        return copy(
            detail = detail.copy(
                leaders = updatedLeaders,
                laggards = updatedLaggards,
            )
        )
    }

    private fun TaxonomyLeader.withRealtimeQuote(quotes: Map<String, RealtimeQuote>): TaxonomyLeader {
        val quote = quotes["${market.name.uppercase()}:${code.uppercase()}"]
        if (quote == null || quote.dataStatus == RealtimeDataStatus.UNAVAILABLE) return this
        val mappedStatus = when (quote.dataStatus) {
            RealtimeDataStatus.LIVE -> DataStatus.LIVE
            RealtimeDataStatus.STALE -> DataStatus.STALE
            RealtimeDataStatus.DELAYED -> DataStatus.DELAYED
            RealtimeDataStatus.UNAVAILABLE -> DataStatus.UNAVAILABLE
        }
        return copy(
            latestClose = quote.lastPrice,
            returnPct = quote.changePercent ?: returnPct,
            dataStatus = mappedStatus,
        )
    }
}
