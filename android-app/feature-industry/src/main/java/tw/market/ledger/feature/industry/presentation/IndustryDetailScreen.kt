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
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import tw.market.ledger.model.TaxonomyMember

@Composable
fun IndustryDetailRoute(
    onSecurityClick: (market: String, code: String) -> Unit,
    viewModel: IndustryDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    IndustryDetailScreen(
        uiState = uiState,
        onSecurityClick = onSecurityClick,
        onRetry = { viewModel.loadDetail() },
    )
}

@Composable
fun IndustryDetailScreen(
    uiState: IndustryDetailUiState,
    onSecurityClick: (market: String, code: String) -> Unit,
    onRetry: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        when (uiState) {
            is IndustryDetailUiState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }

            is IndustryDetailUiState.Error -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(text = uiState.message, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        TextButton(onClick = onRetry) { Text("重試") }
                    }
                }
            }

            is IndustryDetailUiState.Success -> {
                val detail = uiState.detail
                val industry = detail.taxonomy

                Card(modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(text = industry.name, style = MaterialTheme.typography.titleLarge)
                        Text(
                            text = "分類代碼: ${industry.code} | 來源: ${industry.classificationSource}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(
                                text = "成員數量: ${detail.members.size} 檔",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Text(
                                text = "資料狀態: ${detail.dataStatus}",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (detail.isStale) Color(0xFFE65100) else MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }

                if (detail.isStale) {
                    Text(
                        text = "目前顯示離線快取資料 (STALE)",
                        color = Color(0xFFE65100),
                        style = MaterialTheme.typography.labelMedium,
                        modifier = Modifier.padding(bottom = 8.dp),
                    )
                }

                if (detail.members.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("此產業目前無股票成員")
                    }
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(detail.members) { member ->
                            TaxonomyMemberListItem(
                                member = member,
                                onClick = { onSecurityClick(member.market.name, member.code) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun TaxonomyMemberListItem(member: TaxonomyMember, onClick: () -> Unit) {
    val changeVal = member.change?.toDoubleOrNull() ?: 0.0
    val (color, prefix) = when {
        changeVal > 0 -> Color(0xFFD32F2F) to "▲ +"
        changeVal < 0 -> Color(0xFF388E3C) to "▼ "
        else -> MaterialTheme.colorScheme.onSurface to ""
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .testTag("member_item_${member.code}"),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(
                    text = "${member.name} (${member.code})",
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    text = "${member.market.name} | ${member.dataStatus}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = member.close ?: "--",
                    style = MaterialTheme.typography.titleMedium,
                    color = color,
                )
                if (member.change != null && member.changePercent != null) {
                    Text(
                        text = "$prefix${member.change} (${member.changePercent}%)",
                        style = MaterialTheme.typography.bodySmall,
                        color = color,
                    )
                }
            }
        }
    }
}
