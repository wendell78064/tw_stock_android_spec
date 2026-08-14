package tw.market.ledger.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class AnalysisStatementUiModel(
    val type: String,
    val text: String,
    val category: String? = null,
)

data class AIAnalysisUiModel(
    val summary: String,
    val statements: List<AnalysisStatementUiModel>,
    val risks: List<String>,
    val dataCaveats: List<String>,
    val generatedAt: String,
    val provider: String,
    val model: String,
    val groundingAsOf: String,
    val cacheHit: Boolean = false,
)

@Composable
fun AIAnalysisCard(
    analysis: AIAnalysisUiModel?,
    isLoading: Boolean,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "AI 結構化分析",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Surface(
                        color = MaterialTheme.colorScheme.secondaryContainer,
                        shape = RoundedCornerShape(4.dp),
                    ) {
                        Text(
                            text = analysis?.provider ?: "AI",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSecondaryContainer,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        )
                    }
                }
                TextButton(onClick = onRefresh, enabled = !isLoading) {
                    Text(if (analysis == null) "產生分析" else "重新分析")
                }
            }

            if (isLoading) {
                Spacer(modifier = Modifier.height(12.dp))
                SkeletonBox(modifier = Modifier.fillMaxWidth().height(20.dp))
                Spacer(modifier = Modifier.height(8.dp))
                SkeletonBox(modifier = Modifier.fillMaxWidth().height(16.dp))
                Spacer(modifier = Modifier.height(8.dp))
                SkeletonBox(modifier = Modifier.fillMaxWidth().height(16.dp))
            } else if (analysis != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = analysis.summary,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface,
                )

                if (analysis.statements.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = "關鍵觀測與推論",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    analysis.statements.forEach { st ->
                        val prefix = when (st.type) {
                            "FACT" -> "[事實]"
                            "INFERENCE" -> "[推論]"
                            else -> "[警示]"
                        }
                        Text(
                            text = "$prefix ${st.text}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(vertical = 2.dp),
                        )
                    }
                }

                if (analysis.risks.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "潛在風險",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.error,
                    )
                    analysis.risks.forEach { r ->
                        Text(
                            text = "• $r",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(vertical = 1.dp),
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "資料基準: ${TaiwanMarketFormatter.formatTaipeiDateTime(analysis.groundingAsOf)} (AI 產生於 ${TaiwanMarketFormatter.formatTaipeiTime(analysis.generatedAt)})",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            } else {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "點擊「產生分析」獲取基於客觀數據的結構化摘要。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
fun AIConsentDialog(
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("啟用投資組合 AI 摘要") },
        text = {
            Text(
                "啟用後，您的投資組合持股與成本摘要將以去識別化之客觀數據發送至後端 AI 服務以產生分析報告。\n\n" +
                "• 不會包含密碼、金鑰或裝置識別碼\n" +
                "• AI 輸出僅供參考，不構成投資建議\n" +
                "• 您可隨時於設定中關閉此功能"
            )
        },
        confirmButton = {
            Button(onClick = onConfirm) {
                Text("同意並啟用")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )
}
