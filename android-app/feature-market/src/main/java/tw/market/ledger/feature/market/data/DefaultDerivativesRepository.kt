package tw.market.ledger.feature.market.data

import java.io.IOException
import tw.market.ledger.database.*
import tw.market.ledger.feature.market.domain.DerivativesRepository
import tw.market.ledger.model.*
import tw.market.ledger.network.*

class DefaultDerivativesRepository(private val api: DerivativesApi, private val dao: DerivativesDao) : DerivativesRepository {
    override suspend fun overview(product: String): FuturesOverview = try {
        api.overview(product).data.toDomain().also { value ->
            dao.upsert(value.toEntity())
        }
    } catch (error: IOException) {
        dao.overview(product)?.toDomain() ?: throw error
    }

    override suspend fun positions(product: String, window: Int) = api.positions(product, window).data.map {
        FuturesInstitutionalPosition(it.tradeDate, InstitutionType.valueOf(it.institutionType), it.longOi,
            it.shortOi, it.netOi, it.netOiChange, DataStatus.valueOf(it.dataStatus))
    }

    override suspend fun continuous(product: String, range: FuturesRange, rollMethod: RollMethod) =
        api.continuous(product, mapOf(FuturesRange.D5 to "5D", FuturesRange.D10 to "10D",
            FuturesRange.D30 to "30D", FuturesRange.Y1 to "1Y", FuturesRange.Y5 to "5Y").getValue(range),
            rollMethod.name).data.map {
            ContinuousFuturesPoint(it.tradeDate, it.open, it.high, it.low, it.close, it.volume,
                it.openInterest, it.sourceContract, it.rollDate, RollMethod.valueOf(it.rollMethod))
        }
}

private fun FuturesOverviewDto.toDomain() = FuturesOverview(
    FuturesProduct(product.code, product.name, product.contractMultiplier, product.currency, product.isActive),
    near?.toDomain(), next?.toDomain(), DataStatus.valueOf(dataStatus))
private fun FuturesQuoteDto.toDomain() = FuturesQuote(contractCode, contractMonth, tradeDate, open, high,
    low, close, settlementPrice, change, changePercent, volume, openInterest, closeBasis,
    DataStatus.valueOf(dataStatus), asOf)
private fun FuturesOverview.toEntity() = FuturesOverviewEntity(product.code, product.name,
    product.contractMultiplier, product.currency, near?.contractCode, near?.contractMonth,
    near?.tradeDate, near?.close, near?.change, near?.changePercent, near?.volume, near?.openInterest,
    near?.closeBasis, near?.asOf, dataStatus.name)
private fun FuturesOverviewEntity.toDomain(): FuturesOverview {
    val quote = contractCode?.let { FuturesQuote(it, contractMonth.orEmpty(), tradeDate.orEmpty(), null,
        null, null, close, null, change, changePercent, volume, openInterest, closeBasis,
        DataStatus.STALE, asOf.orEmpty()) }
    return FuturesOverview(FuturesProduct(productCode, productName, multiplier, currency, true), quote,
        null, DataStatus.STALE, true)
}
