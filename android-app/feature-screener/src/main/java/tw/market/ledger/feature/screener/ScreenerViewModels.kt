package tw.market.ledger.feature.screener

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.SavedScreener
import tw.market.ledger.model.ScreenerExpression
import tw.market.ledger.model.ScreenerFieldMeta
import tw.market.ledger.model.ScreenerResultSecurity

data class PresetScreener(
    val id: String,
    val name: String,
    val description: String,
    val expression: ScreenerExpression
)

data class ScreenerMainUiState(
    val isLoading: Boolean = false,
    val savedScreeners: List<SavedScreener> = emptyList(),
    val presets: List<PresetScreener> = emptyList(),
    val errorMessage: String? = null
)

@HiltViewModel
class ScreenerMainViewModel @Inject constructor(
    private val repository: ScreenerRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ScreenerMainUiState())
    val uiState: StateFlow<ScreenerMainUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            val saved = repository.getSavedScreeners()
            val defaultPresets = listOf(
                PresetScreener(
                    id = "preset_a",
                    name = "強勢熱門股",
                    description = "產業強度 >= 80 且 股價高於 MA20",
                    expression = ScreenerExpression(
                        type = "AND",
                        children = listOf(
                            ScreenerExpression("CONDITION", "industry_strength_score", "GTE", 80),
                            ScreenerExpression("CONDITION", "close_vs_ma20", "GT", 0)
                        )
                    )
                ),
                PresetScreener(
                    id = "preset_b",
                    name = "法人籌碼雙收",
                    description = "外資5日買超 > 0 且 投信5日買超 > 0",
                    expression = ScreenerExpression(
                        type = "AND",
                        children = listOf(
                            ScreenerExpression("CONDITION", "foreign_5d_net", "GT", 0),
                            ScreenerExpression("CONDITION", "trust_5d_net", "GT", 0)
                        )
                    )
                ),
                PresetScreener(
                    id = "preset_c",
                    name = "支撐超賣股",
                    description = "RSI14 < 35 且 股價高於 MA240",
                    expression = ScreenerExpression(
                        type = "AND",
                        children = listOf(
                            ScreenerExpression("CONDITION", "rsi14", "LT", 35),
                            ScreenerExpression("CONDITION", "close_vs_ma240", "GT", 0)
                        )
                    )
                )
            )
            _uiState.update {
                it.copy(
                    isLoading = false,
                    savedScreeners = saved,
                    presets = defaultPresets
                )
            }
        }
    }

    fun deleteScreener(screener: SavedScreener) {
        viewModelScope.launch {
            val success = repository.deleteSavedScreener(screener.id)
            if (success) {
                loadData()
            }
        }
    }
}

data class ScreenerBuilderUiState(
    val isLoadingFields: Boolean = false,
    val fields: List<ScreenerFieldMeta> = emptyList(),
    val currentExpression: ScreenerExpression = ScreenerExpression("AND", children = emptyList()),
    val screenerName: String = "",
    val screenerDescription: String = "",
    val isSavedSuccess: Boolean = false,
    val errorMessage: String? = null
)

@HiltViewModel
class ScreenerBuilderViewModel @Inject constructor(
    private val repository: ScreenerRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ScreenerBuilderUiState())
    val uiState: StateFlow<ScreenerBuilderUiState> = _uiState.asStateFlow()

    init {
        loadFields()
    }

    fun loadFields() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingFields = true) }
            val fields = repository.getScreenerFields()
            _uiState.update { it.copy(isLoadingFields = false, fields = fields) }
        }
    }

    fun setScreenerName(name: String) {
        _uiState.update { it.copy(screenerName = name) }
    }

    fun setScreenerDescription(desc: String) {
        _uiState.update { it.copy(screenerDescription = desc) }
    }

    fun addCondition(
        fieldId: String,
        operator: String,
        value: Any?,
        value2: Any? = null
    ) {
        val newCondition = ScreenerExpression(
            type = "CONDITION",
            field = fieldId,
            operator = operator,
            value = value,
            value2 = value2
        )
        _uiState.update { current ->
            val updatedChildren = current.currentExpression.children + newCondition
            current.copy(
                currentExpression = current.currentExpression.copy(children = updatedChildren)
            )
        }
    }

    fun addSubGroup(groupType: String) {
        val newGroup = ScreenerExpression(type = groupType, children = emptyList())
        _uiState.update { current ->
            val updatedChildren = current.currentExpression.children + newGroup
            current.copy(
                currentExpression = current.currentExpression.copy(children = updatedChildren)
            )
        }
    }

    fun removeChildNode(index: Int) {
        _uiState.update { current ->
            val children = current.currentExpression.children.toMutableList()
            if (index in children.indices) {
                children.removeAt(index)
            }
            current.copy(
                currentExpression = current.currentExpression.copy(children = children)
            )
        }
    }

    fun saveScreener() {
        val name = _uiState.value.screenerName.trim()
        if (name.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "請輸入篩選器名稱") }
            return
        }
        val expr = _uiState.value.currentExpression
        if (expr.children.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "請至少加入一個篩選條件") }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(errorMessage = null) }
            val res = repository.createSavedScreener(
                name = name,
                description = _uiState.value.screenerDescription.ifEmpty { null },
                expression = expr
            )
            res.onSuccess {
                _uiState.update { state -> state.copy(isSavedSuccess = true) }
            }.onFailure { err ->
                _uiState.update { state -> state.copy(errorMessage = err.message ?: "儲存失敗") }
            }
        }
    }
}

data class ScreenerResultUiState(
    val isLoading: Boolean = false,
    val results: List<ScreenerResultSecurity> = emptyList(),
    val sortField: String = "code",
    val sortDirection: String = "ASC",
    val dataStatus: DataStatus = DataStatus.FINAL,
    val errorMessage: String? = null
)

@HiltViewModel
class ScreenerResultViewModel @Inject constructor(
    private val repository: ScreenerRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ScreenerResultUiState())
    val uiState: StateFlow<ScreenerResultUiState> = _uiState.asStateFlow()

    fun runExpression(expression: ScreenerExpression) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            val res = repository.runScreener(
                expression = expression,
                sortField = _uiState.value.sortField,
                sortDirection = _uiState.value.sortDirection
            )
            res.onSuccess { list ->
                val status = if (list.any { it.dataStatus == DataStatus.STALE }) DataStatus.STALE else DataStatus.FINAL
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        results = list,
                        dataStatus = status
                    )
                }
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = err.message ?: "執行篩選失敗",
                        dataStatus = DataStatus.UNAVAILABLE
                    )
                }
            }
        }
    }

    fun changeSorting(field: String) {
        val newDirection = if (_uiState.value.sortField == field && _uiState.value.sortDirection == "ASC") "DESC" else "ASC"
        _uiState.update { it.copy(sortField = field, sortDirection = newDirection) }
    }
}
