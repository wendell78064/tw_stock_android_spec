package tw.market.ledger.feature.security.data

import tw.market.ledger.database.CandleEntity
import tw.market.ledger.database.TechnicalEntity
import tw.market.ledger.model.Candle
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.IndicatorValue
import tw.market.ledger.model.PriceBasis
import tw.market.ledger.model.TechnicalPoint
import tw.market.ledger.network.CandleDto
import tw.market.ledger.network.TechnicalPointDto

fun CandleDto.toDomain() = Candle(time, open, high, low, close, volumeShares, turnoverAmount)

fun CandleEntity.toDomain() = Candle(time, open, high, low, close, volumeShares, turnoverAmount)

fun Candle.toEntity(
    market: String, code: String, range: String, interval: String, adjustment: String,
    asOf: String, dataStatus: String,
) = CandleEntity(market, code, range, interval, adjustment, time, open, high, low, close,
    volumeShares, turnoverAmount, asOf, dataStatus)

fun TechnicalPointDto.toDomain() = TechnicalPoint(
    tradeDate, PriceBasis.valueOf(priceBasis), algorithmVersion,
    indicators.map { IndicatorValue(it.name, it.value) }, asOf, DataStatus.valueOf(dataStatus),
)

fun TechnicalPoint.toEntities(market: String, code: String): List<TechnicalEntity> = indicators.map {
    TechnicalEntity(market, code, priceBasis.name, tradeDate, it.name, it.value,
        algorithmVersion, asOf, dataStatus.name)
}
