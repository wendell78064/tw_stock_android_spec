package tw.market.ledger.feature.security.presentation

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security

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
    LaunchedEffect(code, market) { viewModel.load(code, market) }
    SecurityDetailScreen(state)
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
