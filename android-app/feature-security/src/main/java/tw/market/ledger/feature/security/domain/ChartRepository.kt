package tw.market.ledger.feature.security.domain

import tw.market.ledger.model.CandleResult
import tw.market.ledger.model.CandleInterval
import tw.market.ledger.model.ChartRange
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.PriceBasis
import tw.market.ledger.model.TechnicalPoint
import tw.market.ledger.model.TechnicalIndicatorPreferences

data class ChartOutcome(
    val candles: CandleResult,
    val technicals: List<TechnicalPoint>,
    val fromCache: Boolean,
)

interface ChartRepository {
    suspend fun load(
        code: String,
        market: MarketCode,
        range: ChartRange,
        interval: CandleInterval,
        basis: PriceBasis,
        preferences: TechnicalIndicatorPreferences,
    ): ChartOutcome
}

class GetSecurityChartUseCase(private val repository: ChartRepository) {
    suspend operator fun invoke(
        code: String,
        market: MarketCode,
        range: ChartRange,
        basis: PriceBasis,
        preferences: TechnicalIndicatorPreferences,
    ): ChartOutcome {
        val interval = if (range == ChartRange.FIVE_YEARS) CandleInterval.WEEK else CandleInterval.DAY
        return repository.load(code, market, range, interval, basis, preferences)
    }
}
