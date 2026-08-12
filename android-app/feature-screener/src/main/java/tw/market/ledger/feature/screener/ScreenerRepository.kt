package tw.market.ledger.feature.screener

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import tw.market.ledger.database.SavedScreenerEntity
import tw.market.ledger.database.ScreenerDao
import tw.market.ledger.database.ScreenerResultEntity
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.SavedScreener
import tw.market.ledger.model.ScreenerExpression
import tw.market.ledger.model.ScreenerFieldMeta
import tw.market.ledger.model.ScreenerResultSecurity
import tw.market.ledger.network.CreateSavedScreenerInputDto
import tw.market.ledger.network.RunScreenerInputDto
import tw.market.ledger.network.ScreenerApi
import tw.market.ledger.network.UpdateSavedScreenerInputDto

@Singleton
class ScreenerRepository @Inject constructor(
    private val api: ScreenerApi,
    private val screenerDao: ScreenerDao
) {
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    suspend fun getScreenerFields(): List<ScreenerFieldMeta> {
        return try {
            val response = api.getScreenerFields()
            if (response.isSuccessful && response.body() != null) {
                response.body()!!.data.map { dto ->
                    ScreenerFieldMeta(
                        fieldId = dto.field_id,
                        label = dto.label,
                        category = dto.category,
                        valueType = dto.value_type,
                        allowedOperators = dto.allowed_operators,
                        unit = dto.unit,
                        supportedWindows = dto.supported_windows
                    )
                }
            } else {
                defaultLocalFields()
            }
        } catch (e: Exception) {
            defaultLocalFields()
        }
    }

    suspend fun runScreener(
        expression: ScreenerExpression,
        sortField: String = "code",
        sortDirection: String = "ASC"
    ): Result<List<ScreenerResultSecurity>> {
        return try {
            val exprMap = expressionToMap(expression)
            val response = api.runScreener(
                RunScreenerInputDto(
                    expression = exprMap,
                    sort_field = sortField,
                    sort_direction = sortDirection
                )
            )
            if (response.isSuccessful && response.body() != null) {
                val results = response.body()!!.data.map { dto ->
                    ScreenerResultSecurity(
                        securityId = UUID.fromString(dto.security_id),
                        code = dto.code,
                        name = dto.name,
                        market = dto.market,
                        industryName = dto.industry_name,
                        themes = dto.themes,
                        close = dto.close,
                        returnPct = dto.return_pct,
                        matchedConditions = dto.matched_conditions,
                        extraMetrics = dto.extra_metrics,
                        dataStatus = try { DataStatus.valueOf(dto.data_status) } catch (e: Exception) { DataStatus.FINAL }
                    )
                }
                cacheResults(results)
                Result.success(results)
            } else {
                val cached = getCachedResults(isStale = true)
                Result.success(cached)
            }
        } catch (e: Exception) {
            val cached = getCachedResults(isStale = true)
            if (cached.isNotEmpty()) {
                Result.success(cached)
            } else {
                Result.failure(e)
            }
        }
    }

    suspend fun getSavedScreeners(): List<SavedScreener> {
        return try {
            val response = api.listSavedScreeners()
            if (response.isSuccessful && response.body() != null) {
                val items = response.body()!!.data.map { dto ->
                    SavedScreener(
                        id = UUID.fromString(dto.id),
                        name = dto.name,
                        description = dto.description,
                        expression = mapToExpression(dto.expression),
                        sortField = dto.sort_field,
                        sortDirection = dto.sort_direction,
                        createdAt = dto.created_at,
                        updatedAt = dto.updated_at
                    )
                }
                cacheSavedScreeners(items)
                items
            } else {
                getCachedSavedScreeners()
            }
        } catch (e: Exception) {
            getCachedSavedScreeners()
        }
    }

    suspend fun createSavedScreener(
        name: String,
        description: String?,
        expression: ScreenerExpression
    ): Result<SavedScreener> {
        return try {
            val response = api.createSavedScreener(
                CreateSavedScreenerInputDto(
                    name = name,
                    description = description,
                    expression = expressionToMap(expression)
                )
            )
            if (response.isSuccessful && response.body() != null) {
                val dto = response.body()!!.data
                val saved = SavedScreener(
                    id = UUID.fromString(dto.id),
                    name = dto.name,
                    description = dto.description,
                    expression = mapToExpression(dto.expression),
                    sortField = dto.sort_field,
                    sortDirection = dto.sort_direction,
                    createdAt = dto.created_at,
                    updatedAt = dto.updated_at
                )
                screenerDao.upsertSavedScreeners(listOf(savedToEntity(saved)))
                Result.success(saved)
            } else {
                Result.failure(Exception("Failed to save screener"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteSavedScreener(id: UUID): Boolean {
        return try {
            val response = api.deleteSavedScreener(id.toString())
            if (response.isSuccessful) {
                screenerDao.deleteSavedScreener(id.toString())
                true
            } else {
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    private suspend fun cacheResults(results: List<ScreenerResultSecurity>) {
        val nowStr = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.TAIWAN).format(Date())

        val entities = results.map { r ->
            ScreenerResultEntity(
                securityId = r.securityId.toString(),
                code = r.code,
                name = r.name,
                market = r.market,
                industryName = r.industryName,
                themesJson = stringListToJson(r.themes),
                close = r.close,
                returnPct = r.returnPct,
                matchedConditionsJson = stringListToJson(r.matchedConditions),
                extraMetricsJson = mapToJson(r.extraMetrics),
                dataStatus = r.dataStatus.name,
                cachedAt = nowStr
            )
        }
        screenerDao.clearScreenerResults()
        screenerDao.replaceCachedScreenerResults(entities)
    }

    private suspend fun getCachedResults(isStale: Boolean): List<ScreenerResultSecurity> {
        val entities = screenerDao.getCachedScreenerResults()

        return entities.map { e ->
            ScreenerResultSecurity(
                securityId = UUID.fromString(e.securityId),
                code = e.code,
                name = e.name,
                market = e.market,
                industryName = e.industryName,
                themes = jsonToStringList(e.themesJson),
                close = e.close,
                returnPct = e.returnPct,
                matchedConditions = jsonToStringList(e.matchedConditionsJson),
                extraMetrics = jsonToMap(e.extraMetricsJson),
                dataStatus = if (isStale) DataStatus.STALE else try { DataStatus.valueOf(e.dataStatus) } catch (err: Exception) { DataStatus.STALE }
            )
        }
    }

    private fun stringListToJson(list: List<String>): String = list.joinToString("||")
    private fun jsonToStringList(str: String): List<String> = if (str.isEmpty()) emptyList() else str.split("||")
    private fun mapToJson(map: Map<String, String?>): String = map.entries.joinToString("||") { "${it.key}::${it.value ?: ""}" }
    private fun jsonToMap(str: String): Map<String, String?> {
        if (str.isEmpty()) return emptyMap()
        return str.split("||").filter { it.contains("::") }.associate {
            val parts = it.split("::", limit = 2)
            parts[0] to parts.getOrNull(1)?.ifEmpty { null }
        }
    }

    private suspend fun cacheSavedScreeners(items: List<SavedScreener>) {
        screenerDao.upsertSavedScreeners(items.map { savedToEntity(it) })
    }

    private suspend fun getCachedSavedScreeners(): List<SavedScreener> {
        val entities = screenerDao.getSavedScreeners()
        return entities.map { e ->
            SavedScreener(
                id = UUID.fromString(e.id),
                name = e.name,
                description = e.description,
                expression = jsonToExpression(e.expressionJson),
                sortField = e.sortField,
                sortDirection = e.sortDirection,
                createdAt = e.updatedAt,
                updatedAt = e.updatedAt
            )
        }
    }

    private fun savedToEntity(saved: SavedScreener): SavedScreenerEntity {
        return SavedScreenerEntity(
            id = saved.id.toString(),
            name = saved.name,
            description = saved.description,
            expressionJson = expressionToJson(saved.expression),
            sortField = saved.sortField,
            sortDirection = saved.sortDirection,
            updatedAt = saved.updatedAt
        )
    }

    @Suppress("UNCHECKED_CAST")
    fun expressionToMap(expr: ScreenerExpression): Map<String, Any?> {
        val res = mutableMapOf<String, Any?>("type" to expr.type)
        if (expr.type == "CONDITION") {
            res["field"] = expr.field
            res["operator"] = expr.operator
            res["value"] = expr.value
            if (expr.value2 != null) res["value2"] = expr.value2
        } else {
            res["children"] = expr.children.map { expressionToMap(it) }
        }
        return res
    }

    @Suppress("UNCHECKED_CAST")
    fun mapToExpression(data: Map<String, Any?>): ScreenerExpression {
        val type = data["type"] as? String ?: "CONDITION"
        if (type == "CONDITION") {
            return ScreenerExpression(
                type = type,
                field = data["field"] as? String,
                operator = data["operator"] as? String,
                value = data["value"],
                value2 = data["value2"]
            )
        }
        val childrenData = data["children"] as? List<Map<String, Any?>> ?: emptyList()
        return ScreenerExpression(
            type = type,
            children = childrenData.map { mapToExpression(it) }
        )
    }

    private fun expressionToJson(expr: ScreenerExpression): String {
        val adapter = moshi.adapter(Any::class.java)
        return adapter.toJson(expressionToMap(expr))
    }

    @Suppress("UNCHECKED_CAST")
    private fun jsonToExpression(json: String): ScreenerExpression {
        val adapter = moshi.adapter(Any::class.java)
        val map = adapter.fromJson(json) as? Map<String, Any?> ?: emptyMap()
        return mapToExpression(map)
    }

    private fun defaultLocalFields(): List<ScreenerFieldMeta> {
        return listOf(
            ScreenerFieldMeta("close", "收盤價", "PRICE_RETURN", "NUMERIC", listOf("GT", "GTE", "LT", "LTE", "BETWEEN", "IS_AVAILABLE")),
            ScreenerFieldMeta("return_1d", "1日漲跌幅", "PRICE_RETURN", "NUMERIC", listOf("GT", "GTE", "LT", "LTE", "BETWEEN")),
            ScreenerFieldMeta("rsi14", "RSI(14)", "TECHNICAL", "NUMERIC", listOf("GT", "GTE", "LT", "LTE", "BETWEEN")),
            ScreenerFieldMeta("close_vs_ma20", "股價相對於 MA20", "TECHNICAL", "NUMERIC", listOf("GT", "GTE", "LT", "LTE")),
            ScreenerFieldMeta("foreign_5d_net", "外資5日累計買賣超", "INSTITUTIONAL", "NUMERIC", listOf("GT", "GTE", "LT", "LTE")),
            ScreenerFieldMeta("margin_balance_change", "融資餘額變動", "CREDIT", "NUMERIC", listOf("GT", "GTE", "LT", "LTE")),
            ScreenerFieldMeta("industry_name", "官方產業名稱", "TAXONOMY", "TEXT", listOf("EQ", "NE", "IN", "NOT_IN")),
            ScreenerFieldMeta("theme_name", "自訂題材名稱", "TAXONOMY", "TEXT", listOf("EQ", "NE", "IN", "NOT_IN")),
            ScreenerFieldMeta("industry_strength_score", "產業強度分數", "INDUSTRY_STRENGTH", "NUMERIC", listOf("GT", "GTE", "LT", "LTE", "BETWEEN"))
        )
    }
}
