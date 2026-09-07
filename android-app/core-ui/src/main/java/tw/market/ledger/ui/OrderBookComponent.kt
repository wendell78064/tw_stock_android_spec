package tw.market.ledger.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import tw.market.ledger.model.RealtimeDataStatus
import java.math.BigDecimal

data class OrderBookLevel(
    val levelName: String,
    val price: String?,
    val volume: Int?,
    val isAsk: Boolean,
)

data class OrderBookUiModel(
    val asks: List<OrderBookLevel>, // Top to bottom: 賣五, 賣四, 賣三, 賣二, 賣一
    val bids: List<OrderBookLevel>, // Top to bottom: 買一, 買二, 買三, 買四, 買五
    val status: RealtimeDataStatus,
    val referencePrice: BigDecimal? = null,
)

object OrderBookMapper {
    private val ASK_NAMES = listOf("賣一", "賣二", "賣三", "賣四", "賣五")
    private val BID_NAMES = listOf("買一", "買二", "買三", "買四", "買五")

    fun map(
        bidPrices: List<String>,
        bidVolumes: List<Int>,
        askPrices: List<String>,
        askVolumes: List<Int>,
        status: RealtimeDataStatus = RealtimeDataStatus.LIVE,
        referencePrice: BigDecimal? = null,
    ): OrderBookUiModel {
        val count = maxOf(bidPrices.size, askPrices.size).coerceAtMost(5).coerceAtLeast(1)

        val askLevels = mutableListOf<OrderBookLevel>()
        for (i in 0 until count) {
            val name = ASK_NAMES.getOrElse(i) { "賣${i + 1}" }
            val price = askPrices.getOrNull(i)?.takeIf { it.isNotBlank() }
            val vol = askVolumes.getOrNull(i)
            askLevels.add(OrderBookLevel(name, price, vol, isAsk = true))
        }

        val bidLevels = mutableListOf<OrderBookLevel>()
        for (i in 0 until count) {
            val name = BID_NAMES.getOrElse(i) { "買${i + 1}" }
            val price = bidPrices.getOrNull(i)?.takeIf { it.isNotBlank() }
            val vol = bidVolumes.getOrNull(i)
            bidLevels.add(OrderBookLevel(name, price, vol, isAsk = false))
        }

        // Asks are displayed top-to-bottom: 賣五 down to 賣一
        return OrderBookUiModel(
            asks = askLevels.reversed(),
            bids = bidLevels,
            status = status,
            referencePrice = referencePrice,
        )
    }
}

@Composable
fun OrderBookSection(
    uiModel: OrderBookUiModel?,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .testTag("order-book-card"),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f)
        ),
        shape = RoundedCornerShape(8.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "五檔報價",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                if (uiModel != null) {
                    val (statusColor, statusText) = when (uiModel.status) {
                        RealtimeDataStatus.LIVE -> Color(0xFF2E7D32) to "即時"
                        RealtimeDataStatus.STALE -> Color(0xFFE65100) to "盤後/延遲"
                        RealtimeDataStatus.DELAYED -> Color(0xFFE65100) to "延遲"
                        RealtimeDataStatus.UNAVAILABLE -> Color.Gray to "未提供"
                    }
                    Text(
                        text = statusText,
                        color = statusColor,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.testTag("order-book-status-badge"),
                    )
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            if (uiModel == null) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 16.dp)
                        .testTag("order-book-loading"),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "即時五檔資料載入中...",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                val hasAnyData = uiModel.asks.any { it.price != null || it.volume != null } ||
                    uiModel.bids.any { it.price != null || it.volume != null }

                if (!hasAnyData) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 12.dp)
                            .testTag("order-book-empty"),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = "目前無委託掛單資料",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                } else {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("order-book-levels-container"),
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        // Header row
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 2.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(
                                text = "檔位",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.weight(1f),
                            )
                            Text(
                                text = "委託價",
                                style = MaterialTheme.typography.labelSmall,
                                textAlign = TextAlign.End,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.weight(1.5f),
                            )
                            Text(
                                text = "張數",
                                style = MaterialTheme.typography.labelSmall,
                                textAlign = TextAlign.End,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.weight(1.2f),
                            )
                        }

                        // Asks (賣五 down to 賣一)
                        uiModel.asks.forEach { level ->
                            OrderBookRow(
                                level = level,
                                referencePrice = uiModel.referencePrice,
                                modifier = Modifier.testTag("order-book-ask-${level.levelName}"),
                            )
                        }

                        HorizontalDivider(
                            modifier = Modifier.padding(vertical = 4.dp),
                            thickness = 1.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f),
                        )

                        // Bids (買一 down to 買五)
                        uiModel.bids.forEach { level ->
                            OrderBookRow(
                                level = level,
                                referencePrice = uiModel.referencePrice,
                                modifier = Modifier.testTag("order-book-bid-${level.levelName}"),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OrderBookRow(
    level: OrderBookLevel,
    referencePrice: BigDecimal?,
    modifier: Modifier = Modifier,
) {
    val priceText = level.price?.let {
        val bd = it.toBigDecimalOrNull()
        if (bd != null) TaiwanMarketFormatter.formatPrice(bd) else it
    } ?: "--"

    val volumeText = level.volume?.let {
        TaiwanMarketFormatter.formatShares(it.toLong())
    } ?: "--"

    val priceColor = if (level.price != null && referencePrice != null) {
        val parsed = level.price.toBigDecimalOrNull()
        if (parsed != null) {
            when {
                parsed > referencePrice -> Color(0xFFD32F2F)
                parsed < referencePrice -> Color(0xFF388E3C)
                else -> MaterialTheme.colorScheme.onSurface
            }
        } else {
            MaterialTheme.colorScheme.onSurface
        }
    } else {
        MaterialTheme.colorScheme.onSurface
    }

    val sideColor = if (level.isAsk) Color(0xFF388E3C) else Color(0xFFD32F2F)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = "${level.levelName}, 價格 $priceText, 委託量 $volumeText 張"
            }
            .padding(vertical = 1.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = level.levelName,
            style = MaterialTheme.typography.bodySmall,
            color = sideColor,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.weight(1f),
        )
        Text(
            text = priceText,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
            color = priceColor,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.End,
            modifier = Modifier.weight(1.5f),
        )
        Text(
            text = volumeText,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.End,
            modifier = Modifier.weight(1.2f),
        )
    }
}
