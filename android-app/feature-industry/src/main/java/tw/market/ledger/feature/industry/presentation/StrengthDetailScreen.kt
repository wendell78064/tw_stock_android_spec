package tw.market.ledger.feature.industry.presentation

import androidx.compose.foundation.Canvas
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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import tw.market.ledger.model.TaxonomyLeader
import tw.market.ledger.model.TaxonomyStrength

@Composable
fun StrengthDetailRoute(
    id: String,
    isIndustryTaxonomy: Boolean,
    onSecurityClick: (String, String) -> Unit,
    viewModel: StrengthDetailViewModel = hiltViewModel(),
) {
    androidx.compose.runtime.LaunchedEffect(id, isIndustryTaxonomy) {
        viewModel.load(id, isIndustryTaxonomy)
    }
    DisposableEffect(viewModel) {
        viewModel.activateRealtime()
        onDispose(viewModel::deactivateRealtime)
    }
    val uiState by viewModel.uiState.collectAsState()
    StrengthDetailScreen(
        uiState = uiState,
        onWindowSelect = viewModel::setWindow,
        onSecurityClick = onSecurityClick,
        onRetry = { viewModel.load(id, isIndustryTaxonomy) },
    )
}

@Composable
fun StrengthDetailScreen(
    uiState: StrengthDetailUiState,
    onWindowSelect: (Int) -> Unit,
    onSecurityClick: (String, String) -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxSize().padding(16.dp)) {
        when (uiState) {
            is StrengthDetailUiState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(modifier = Modifier.testTag("strength_detail_loading"))
                }
            }
            is StrengthDetailUiState.Error -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(text = uiState.message, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = onRetry, modifier = Modifier.testTag("detail_retry_button")) {
                            Text("重試")
                        }
                    }
                }
            }
            is StrengthDetailUiState.Success -> {
                val snap = uiState.detail.snapshot

                Text(
                    text = "${snap.taxonomyName} (${snap.taxonomyCode}) - 強度明細",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.testTag("strength_detail_title"),
                )

                Spacer(modifier = Modifier.height(8.dp))

                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val windows = listOf(1, 5, 10, 20, 60)
                    items(windows) { w ->
                        FilterChip(
                            selected = uiState.window == w,
                            onClick = { onWindowSelect(w) },
                            label = { Text("${w}D") },
                            modifier = Modifier.testTag("chip_detail_window_$w"),
                        )
                    }
                }

                if (uiState.isStale) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "⚠️ 離線快取資料 (STALE)",
                        color = MaterialTheme.colorScheme.tertiary,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                LazyColumn(
                    modifier = Modifier.testTag("strength_detail_lazy_column"),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        // Summary Card
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    modifier = Modifier.fillMaxWidth(),
                                ) {
                                    Text(
                                        text = "綜合強度分數: ${snap.strengthScore ?: "N/A"}",
                                        fontSize = 20.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                                    )
                                    Text(
                                        text = snap.rank?.let { "排名 #${it}" } ?: "未排名",
                                        fontSize = 18.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                                    )
                                }
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = "演算法版本: ${snap.algorithmVersion} (涵蓋率: ${(snap.componentCoverage.toDoubleOrNull() ?: 0.0) * 100}%)",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                                )
                            }
                        }
                    }

                    item {
                        // Component Scores Breakdown
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("5大成分分數拆解", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                                Spacer(modifier = Modifier.height(8.dp))
                                val c = snap.components
                                ComponentRow("動能 (30%)", c.momentumScore)
                                ComponentRow("廣度 (25%)", c.breadthScore)
                                ComponentRow("技術面 (20%)", c.technicalScore)
                                ComponentRow("籌碼流向 (15%)", c.institutionalScore)
                                ComponentRow("成交量 (10%)", c.turnoverScore)
                            }
                        }
                    }

                    item {
                        // Strength History Trend Line (Compose Canvas)
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("近 60 日強度趨勢", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                                Spacer(modifier = Modifier.height(8.dp))
                                StrengthCanvasChart(
                                    history = uiState.history,
                                    modifier = Modifier.fillMaxWidth().height(140.dp).testTag("strength_canvas_chart"),
                                )
                            }
                        }
                    }

                    item {
                        // Leaders (Top 5)
                        Text("領漲股 (Leaders Top 5)", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    }

                    items(uiState.detail.leaders) { leader ->
                        LeaderRow(leader = leader, onClick = { onSecurityClick(leader.market.name, leader.code) })
                    }

                    item {
                        // Laggards (Bottom 5)
                        Text("領跌股 (Laggards Bottom 5)", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    }

                    items(uiState.detail.laggards) { laggard ->
                        LeaderRow(leader = laggard, onClick = { onSecurityClick(laggard.market.name, laggard.code) })
                    }
                }
            }
        }
    }
}

@Composable
fun ComponentRow(label: String, score: String?) {
    Row(
        horizontalArrangement = Arrangement.SpaceBetween,
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Text(
            score ?: "N/A (標示未提供)",
            fontWeight = FontWeight.SemiBold,
            color = if (score != null) MaterialTheme.colorScheme.primary else Color.Gray,
        )
    }
}

@Composable
fun LeaderRow(leader: TaxonomyLeader, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).testTag("leader_item_${leader.code}"),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("${leader.name} (${leader.code})", fontWeight = FontWeight.Bold)
                Text("最新收盤: ${leader.latestClose ?: "--"} · ${leader.dataStatus}", style = MaterialTheme.typography.bodySmall)
            }
            Text(
                text = "${leader.returnPct}%",
                fontWeight = FontWeight.Bold,
                color = if ((leader.returnPct.toDoubleOrNull() ?: 0.0) >= 0) Color.Red else Color.Green,
            )
        }
    }
}

@Composable
fun StrengthCanvasChart(
    history: List<TaxonomyStrength>,
    modifier: Modifier = Modifier,
) {
    val primaryColor = MaterialTheme.colorScheme.primary
    Canvas(modifier = modifier) {
        if (history.isEmpty()) return@Canvas

        val scores = history.mapNotNull { it.strengthScore?.toFloatOrNull() }
        if (scores.isEmpty()) return@Canvas

        val minScore = 0f
        val maxScore = 100f
        val stepX = size.width / (scores.size - 1).coerceAtLeast(1)

        val path = Path()
        scores.forEachIndexed { index, score ->
            val x = index * stepX
            val y = size.height - ((score - minScore) / (maxScore - minScore) * size.height)
            if (index == 0) {
                path.moveTo(x, y)
            } else {
                path.lineTo(x, y)
            }
            drawCircle(color = primaryColor, radius = 3.dp.toPx(), center = Offset(x, y))
        }

        drawPath(path = path, color = primaryColor, style = Stroke(width = 2.dp.toPx()))
    }
}
