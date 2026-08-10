package tw.market.ledger.feature.security.data

import java.io.IOException
import tw.market.ledger.database.ChartDao
import tw.market.ledger.feature.security.domain.ChartOutcome
import tw.market.ledger.feature.security.domain.ChartRepository
import tw.market.ledger.model.CandleInterval
import tw.market.ledger.model.CandleResult
import tw.market.ledger.model.ChartRange
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.IndicatorValue
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.PriceBasis
import tw.market.ledger.model.TechnicalPoint
import tw.market.ledger.model.TechnicalIndicatorPreferences
import tw.market.ledger.network.ChartApi

class DefaultChartRepository(
    private val api: ChartApi,
    private val dao: ChartDao,
) : ChartRepository {
    override suspend fun load(
        code: String, market: MarketCode, range: ChartRange, interval: CandleInterval,
        basis: PriceBasis, preferences: TechnicalIndicatorPreferences,
    ): ChartOutcome = try {
        val apiRange = range.apiValue()
        val candleEnvelope = api.candles(code, market.name, apiRange, interval.apiValue, basis.name)
        val names = preferences.enabled.map { name ->
            when { name.startsWith("RSI") -> "RSI${preferences.rsi.period}"
                name.startsWith("ATR") -> "ATR${preferences.atr.period}" else -> name }
        }.toSet()
        val technicalEnvelope = api.technicals(code, market.name, basis.name,
            names.joinToString(","), preferences.queryParameters())
        val candles = candleEnvelope.data.map { it.toDomain() }
        val technicals = technicalEnvelope.data.map { it.toDomain() }
        dao.clearCandles(market.name, code, apiRange, interval.apiValue, basis.name)
        dao.upsertCandles(candles.map { it.toEntity(market.name, code, apiRange, interval.apiValue,
            basis.name, candleEnvelope.meta.asOf, candleEnvelope.meta.dataStatus) })
        dao.upsertTechnicals(technicals.flatMap { it.toEntities(market.name, code) })
        ChartOutcome(CandleResult(candles, candleEnvelope.meta.asOf,
            DataStatus.valueOf(candleEnvelope.meta.dataStatus), candleEnvelope.meta.source,
            candleEnvelope.displayNote), technicals, false)
    } catch (error: IOException) {
        val apiRange = range.apiValue()
        val cached = dao.candles(market.name, code, apiRange, interval.apiValue, basis.name)
        if (cached.isEmpty()) throw error
        val rows = dao.technicals(market.name, code, basis.name)
        val technicals = rows.groupBy { it.tradeDate }.map { (tradeDate, values) ->
            val first = values.first()
            TechnicalPoint(tradeDate, basis, first.algorithmVersion,
                values.map { IndicatorValue(it.name, it.value) }, first.asOf, DataStatus.STALE)
        }
        ChartOutcome(CandleResult(cached.map { it.toDomain() }, cached.maxOf { it.asOf },
            DataStatus.STALE, "ROOM_CACHE", "離線快取；非最新資料"), technicals, true)
    }
}

private fun ChartRange.apiValue() = when (this) {
    ChartRange.ONE_DAY -> "1D"
    ChartRange.FIVE_DAYS -> "5D"
    ChartRange.TEN_DAYS -> "10D"
    ChartRange.THIRTY_DAYS -> "30D"
    ChartRange.ONE_YEAR -> "1Y"
    ChartRange.FIVE_YEARS -> "5Y"
}
