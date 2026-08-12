package tw.market.ledger.model

import java.util.UUID

enum class ScreenerOperator {
    GT, GTE, LT, LTE, EQ, NE, BETWEEN, IN, NOT_IN, IS_AVAILABLE, IS_UNAVAILABLE
}

enum class FilterCategory {
    PRICE_RETURN, TECHNICAL, INSTITUTIONAL, CREDIT, TAXONOMY, INDUSTRY_STRENGTH
}

data class ScreenerFieldMeta(
    val fieldId: String,
    val label: String,
    val category: String,
    val valueType: String,
    val allowedOperators: List<String>,
    val unit: String? = null,
    val supportedWindows: List<Int>? = null
)

data class ScreenerExpression(
    val type: String, // "CONDITION", "AND", "OR"
    val field: String? = null,
    val operator: String? = null,
    val value: Any? = null,
    val value2: Any? = null,
    val children: List<ScreenerExpression> = emptyList()
)

data class SavedScreener(
    val id: UUID,
    val name: String,
    val description: String? = null,
    val expression: ScreenerExpression,
    val sortField: String = "code",
    val sortDirection: String = "ASC",
    val createdAt: String,
    val updatedAt: String
)

data class ScreenerResultSecurity(
    val securityId: UUID,
    val code: String,
    val name: String,
    val market: String,
    val industryName: String? = null,
    val themes: List<String> = emptyList(),
    val close: String? = null,
    val returnPct: String? = null,
    val matchedConditions: List<String> = emptyList(),
    val extraMetrics: Map<String, String?> = emptyMap(),
    val dataStatus: DataStatus = DataStatus.FINAL
)
