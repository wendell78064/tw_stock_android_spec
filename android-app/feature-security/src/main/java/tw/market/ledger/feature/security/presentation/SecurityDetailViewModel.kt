package tw.market.ledger.feature.security.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import java.util.concurrent.atomic.AtomicLong
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.feature.security.domain.GetSecurityUseCase
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.RealtimeQuote
import tw.market.ledger.model.Security
import tw.market.ledger.network.RealtimeSubscriptionManager

sealed interface SecurityDetailUiState {
    data object Loading : SecurityDetailUiState
    data class Error(val message: String) : SecurityDetailUiState
    data class Offline(val message: String) : SecurityDetailUiState
    data class Stale(val security: Security) : SecurityDetailUiState
    data class Success(val security: Security) : SecurityDetailUiState
}

@HiltViewModel
class SecurityDetailViewModel @Inject constructor(
    private val detail: GetSecurityUseCase,
    private val subscriptionManager: RealtimeSubscriptionManager
) : ViewModel() {
    private companion object {
        val nextOwnerId = AtomicLong()
    }

    private data class Target(val code: String, val market: MarketCode)

    private val _uiState = MutableStateFlow<SecurityDetailUiState>(SecurityDetailUiState.Loading)
    val uiState: StateFlow<SecurityDetailUiState> = _uiState.asStateFlow()

    private val _realtimeQuote = MutableStateFlow<RealtimeQuote?>(null)
    val realtimeQuote: StateFlow<RealtimeQuote?> = _realtimeQuote.asStateFlow()
    private val ownerId = "p2-current-view:${nextOwnerId.incrementAndGet()}"
    private var target: Target? = null
    private var quoteJob: Job? = null

    fun load(code: String, market: MarketCode) {
        val nextTarget = Target(code.uppercase(), market)
        if (target != nextTarget) {
            releaseTarget()
            target = nextTarget
            _realtimeQuote.value = null
            subscriptionManager.acquireCurrentView(ownerId, market.name, code)
            quoteJob = viewModelScope.launch {
                subscriptionManager.latestQuotes.collect { map ->
                    val active = target ?: return@collect
                    _realtimeQuote.value =
                        map["${active.market.name}:${active.code}"] ?: _realtimeQuote.value
                }
            }
        }

        viewModelScope.launch {
            _uiState.value = SecurityDetailUiState.Loading
            try {
                val outcome = detail(code, market)
                _uiState.value = if (outcome.fromCache) SecurityDetailUiState.Stale(outcome.security)
                    else SecurityDetailUiState.Success(outcome.security)
            } catch (_: IOException) {
                _uiState.value = SecurityDetailUiState.Offline("目前離線，且沒有可用快取")
            } catch (error: Exception) {
                _uiState.value = SecurityDetailUiState.Error(error.message ?: "載入失敗")
            }

        }
    }

    fun leave(code: String, market: MarketCode) {
        if (target == Target(code.uppercase(), market)) releaseTarget()
    }

    private fun releaseTarget() {
        val current = target ?: return
        subscriptionManager.releaseCurrentView(ownerId, current.market.name, current.code)
        target = null
        quoteJob?.cancel()
        quoteJob = null
        _realtimeQuote.value = null
    }

    override fun onCleared() {
        releaseTarget()
        super.onCleared()
    }
}
