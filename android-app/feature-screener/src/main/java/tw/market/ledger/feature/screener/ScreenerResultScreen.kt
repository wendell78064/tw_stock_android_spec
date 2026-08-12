package tw.market.ledger.feature.screener

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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.ScreenerExpression
import tw.market.ledger.model.ScreenerResultSecurity

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScreenerResultScreen(
    viewModel: ScreenerResultViewModel,
    expression: ScreenerExpression?,
    onOpenSecurityDetail: (String, String) -> Unit = { _, _ -> }
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(expression) {
        if (expression != null) {
            viewModel.runExpression(expression)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("篩選結果 (${uiState.results.size})") }
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            if (uiState.isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center).testTag("result_loading")
                )
            } else {
                Column(modifier = Modifier.fillMaxSize()) {
                    if (uiState.dataStatus == DataStatus.STALE) {
                        Surface(
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("stale_banner"),
                            color = MaterialTheme.colorScheme.tertiaryContainer
                        ) {
                            Text(
                                text = "離線狀態：目前呈現歷史快取結果 (STALE)",
                                modifier = Modifier.padding(12.dp),
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onTertiaryContainer
                            )
                        }
                    }

                    if (uiState.results.isEmpty()) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .testTag("empty_screener_results"),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = uiState.errorMessage ?: "查無符合條件之股票",
                                style = MaterialTheme.typography.bodyLarge
                            )
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            items(uiState.results, key = { it.securityId.toString() }) { security ->
                                ScreenerResultItemCard(
                                    security = security,
                                    onClick = { onOpenSecurityDetail(security.code, security.market) }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ScreenerResultItemCard(
    security: ScreenerResultSecurity,
    onClick: () -> Unit
) {
    var expanded by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
            .testTag("result_item_${security.code}"),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = RoundedCornerShape(4.dp),
                        color = MaterialTheme.colorScheme.secondaryContainer
                    ) {
                        Text(
                            text = security.market,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall
                        )
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "${security.name} (${security.code})",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.testTag("security_code_${security.code}")
                    )
                }

                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = security.close ?: "--",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = if (security.returnPct != null) "${security.returnPct}%" else "--",
                        style = MaterialTheme.typography.bodySmall,
                        color = if ((security.returnPct?.toDoubleOrNull() ?: 0.0) >= 0) Color.Red else Color(0xFF008000)
                    )
                }
            }

            val ind = security.industryName
            if (!ind.isNullOrEmpty()) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "產業: $ind",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Matched conditions expander
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded },
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "符合條件 (${security.matchedConditions.size})",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(
                    text = if (expanded) "隱藏 ▲" else "展開 ▼",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )
            }

            if (expanded) {
                Spacer(modifier = Modifier.height(6.dp))
                security.matchedConditions.forEach { cond ->
                    Text(
                        text = "✓ $cond",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.padding(vertical = 2.dp)
                    )
                }
            }
        }
    }
}
