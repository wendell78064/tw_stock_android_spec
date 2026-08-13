package tw.market.ledger.feature.industry.presentation

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.FilterChip
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import tw.market.ledger.model.Industry
import tw.market.ledger.model.Theme

@Composable
fun IndustryLandingRoute(
    onIndustryClick: (String) -> Unit,
    onThemeClick: (String) -> Unit,
    viewModel: IndustryLandingViewModel = hiltViewModel(),
    realtimeViewModel: IndustryRealtimeViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val realtime by realtimeViewModel.state.collectAsStateWithLifecycle()
    Column { IndustryRealtimePanel(realtime, realtimeViewModel::setType); Box(Modifier.weight(1f)) { IndustryLandingScreen(
        uiState = uiState,
        onIndustryClick = onIndustryClick,
        onThemeClick = onThemeClick,
        onRetry = { viewModel.loadData() },
    ) } }
}

@Composable
fun IndustryRealtimePanel(state: IndustryRealtimeUiState, onType: (Boolean) -> Unit) {
    Card(Modifier.fillMaxWidth().padding(12.dp).testTag("realtime-strength-panel")) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("強度模式：盤中", style = MaterialTheme.typography.titleMedium)
                Text("盤後：twml-industry-strength-v1")
            }
            when (state) {
                IndustryRealtimeUiState.Loading -> CircularProgressIndicator()
                IndustryRealtimeUiState.Unavailable -> Text("即時產業強度尚未配置")
                is IndustryRealtimeUiState.Content -> {
                    Row { FilterChip(state.industry, { onType(true) }, { Text("盤中產業") }); FilterChip(!state.industry, { onType(false) }, { Text("盤中題材") }) }
                    if (state.stale) Text("STALE · 顯示最後 snapshot")
                    state.rows.take(5).forEach { item ->
                        Text("#${item.rank ?: "--"} ${item.name} 分數 ${item.realtimeStrengthScore ?: "N/A"} · 報酬 ${item.equalWeightReturn ?: "--"}%")
                        Text("上漲比 ${item.advanceRatio ?: "--"} · MA20 ${item.aboveMa20PctRealtime ?: "unavailable"} · coverage ${item.coverageRatio} · ${item.dataStatus}")
                        Text("Momentum ${item.components.momentum ?: "unavailable"} · Breadth ${item.components.breadth ?: "unavailable"} · Technical ${item.components.technical ?: "unavailable"} · Turnover ${item.components.turnover ?: "unavailable"}")
                    }
                }
            }
        }
    }
}

@Composable
fun IndustryLandingScreen(
    uiState: IndustryLandingUiState,
    onIndustryClick: (String) -> Unit,
    onThemeClick: (String) -> Unit,
    onRetry: () -> Unit,
) {
    var selectedTab by remember { mutableIntStateOf(0) }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        TabRow(selectedTabIndex = selectedTab) {
            Tab(
                selected = selectedTab == 0,
                onClick = { selectedTab = 0 },
                text = { Text("官方產業") },
                modifier = Modifier.testTag("tab_official_industry"),
            )
            Tab(
                selected = selectedTab == 1,
                onClick = { selectedTab = 1 },
                text = { Text("自訂題材") },
                modifier = Modifier.testTag("tab_custom_theme"),
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        when (uiState) {
            is IndustryLandingUiState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }

            is IndustryLandingUiState.Error -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(text = uiState.message, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        TextButton(onClick = onRetry) { Text("重試") }
                    }
                }
            }

            is IndustryLandingUiState.Success -> {
                if (uiState.isStale) {
                    Card(modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
                        Text(
                            text = "注意：現為離線快取資料 (STALE)",
                            color = Color(0xFFE65100),
                            modifier = Modifier.padding(12.dp),
                        )
                    }
                }

                if (selectedTab == 0) {
                    if (uiState.industries.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("無可用產業分類")
                        }
                    } else {
                        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(uiState.industries) { industry ->
                                IndustryListItem(industry = industry, onClick = { onIndustryClick(industry.id) })
                            }
                        }
                    }
                } else {
                    if (uiState.themes.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("無可用題材分類")
                        }
                    } else {
                        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(uiState.themes) { theme ->
                                ThemeListItem(theme = theme, onClick = { onThemeClick(theme.id) })
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun IndustryListItem(industry: Industry, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .testTag("industry_item_${industry.code}"),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(text = industry.name, style = MaterialTheme.typography.titleMedium)
                Text(
                    text = "代碼: ${industry.code} | 來源: ${industry.classificationSource}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                text = "${industry.memberCount} 檔",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
fun ThemeListItem(theme: Theme, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .testTag("theme_item_${theme.code}"),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = theme.name, style = MaterialTheme.typography.titleMedium)
                theme.description?.let { desc ->
                    Text(
                        text = desc,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = "類型: ${theme.classificationType}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
            Text(
                text = "${theme.memberCount} 檔",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}
