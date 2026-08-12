package tw.market.ledger.feature.industry.presentation

import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.TaxonomyStrength

@Composable
fun StrengthRankingScreen(
    uiState: StrengthRankingUiState,
    onWindowSelect: (Int) -> Unit,
    onSortSelect: (String) -> Unit,
    onTabSelect: (Boolean) -> Unit,
    onTaxonomyClick: (String, Boolean) -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxSize().padding(16.dp)) {
        Text(
            text = "產業與題材強弱排行",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.testTag("strength_ranking_title"),
        )
        Spacer(modifier = Modifier.height(12.dp))

        when (uiState) {
            is StrengthRankingUiState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(modifier = Modifier.testTag("strength_loading"))
                }
            }
            is StrengthRankingUiState.Error -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(text = uiState.message, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = onRetry, modifier = Modifier.testTag("strength_retry_button")) {
                            Text("重試")
                        }
                    }
                }
            }
            is StrengthRankingUiState.Success -> {
                // Tab Selection
                TabRow(selectedTabIndex = if (uiState.isIndustry) 0 else 1) {
                    Tab(
                        selected = uiState.isIndustry,
                        onClick = { onTabSelect(true) },
                        modifier = Modifier.testTag("tab_official_strength"),
                    ) {
                        Text("官方產業", modifier = Modifier.padding(12.dp))
                    }
                    Tab(
                        selected = !uiState.isIndustry,
                        onClick = { onTabSelect(false) },
                        modifier = Modifier.testTag("tab_custom_strength"),
                    ) {
                        Text("自訂題材", modifier = Modifier.padding(12.dp))
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Window Chips
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val windows = listOf(1, 5, 10, 20, 60)
                    items(windows) { w ->
                        FilterChip(
                            selected = uiState.window == w,
                            onClick = { onWindowSelect(w) },
                            label = { Text("${w}D") },
                            modifier = Modifier.testTag("chip_window_$w"),
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Sort Chips
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val sorts = listOf(
                        "strength" to "綜合分數",
                        "return" to "等權報酬",
                        "breadth" to "上漲比例",
                        "foreign_flow" to "外資買賣超",
                        "turnover" to "成交量",
                    )
                    items(sorts) { (key, label) ->
                        FilterChip(
                            selected = uiState.sort == key,
                            onClick = { onSortSelect(key) },
                            label = { Text(label) },
                            modifier = Modifier.testTag("chip_sort_$key"),
                        )
                    }
                }

                if (uiState.isStale) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "⚠️ 網路異常，目前呈現離線快取資料 (STALE)",
                        color = MaterialTheme.colorScheme.tertiary,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.testTag("stale_warning"),
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                if (uiState.strengths.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("暫無強度排行資料")
                    }
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(uiState.strengths) { item ->
                            StrengthRankingRow(
                                item = item,
                                onClick = { onTaxonomyClick(item.taxonomyId, uiState.isIndustry) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun StrengthRankingRow(
    item: TaxonomyStrength,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).testTag("strength_item_${item.taxonomyCode}"),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = item.rank?.let { "#$it" } ?: "--",
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp,
                    color = MaterialTheme.colorScheme.primary,
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "${item.taxonomyName} (${item.taxonomyCode})",
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        text = "成員: ${item.validMembers}/${item.totalMembers} | 上漲: ${item.advancers} 下跌: ${item.decliners}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(if (item.strengthScore != null) MaterialTheme.colorScheme.primaryContainer else Color.Gray)
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                ) {
                    Text(
                        text = item.strengthScore ?: "N/A",
                        fontWeight = FontWeight.Bold,
                        color = if (item.strengthScore != null) MaterialTheme.colorScheme.onPrimaryContainer else Color.White,
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "報酬: ${item.equalWeightReturn}%",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = "MA20>: ${(item.aboveMa20Pct.toDoubleOrNull() ?: 0.0) * 100}%",
                    style = MaterialTheme.typography.bodySmall,
                )
                Text(
                    text = "外資: ${item.foreignNetAmount}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
