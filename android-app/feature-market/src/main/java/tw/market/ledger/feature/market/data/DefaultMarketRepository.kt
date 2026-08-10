package tw.market.ledger.feature.market.data

import java.io.IOException
import tw.market.ledger.database.*
import tw.market.ledger.feature.market.domain.MarketRepository
import tw.market.ledger.model.*
import tw.market.ledger.network.*

class DefaultMarketRepository(private val api: MarketApi, private val dao: MarketDao) : MarketRepository {
    override suspend fun overview(): MarketOverview = try {
        val response = api.overview(); val result = response.toDomain(false)
        dao.upsertIndexes(response.data.indexes.map { it.toEntity() })
        dao.upsertBreadth(response.data.breadth.map { it.toEntity() })
        dao.upsertInstitutional(response.data.institutionalSpot.map { it.toEntity("MARKET", 1) })
        dao.upsertCredit(response.data.credit.map { it.toEntity("MARGIN", "", 1) })
        dao.upsertCredit(response.data.lending.map { it.toEntity("LENDING", "", 1) })
        result
    } catch (error: IOException) {
        val indexes = dao.latestIndexes(); val breadth = dao.latestBreadth()
        if (indexes.isEmpty()) throw error
        MarketOverview(indexes.map { it.toDomain() }, breadth.map { it.toDomain() }, emptyList(),
            emptyList(), emptyList(), indexes.maxOf { it.asOf }, DataStatus.STALE, true)
    }
    override suspend fun marketInstitutional(market: MarketCode, window: Int) = try {
        api.marketInstitutional(market.name, window).data.also { rows ->
            dao.upsertInstitutional(rows.map { it.toEntity("MARKET", window) })
        }.map { it.toDomain() }
    } catch (error: IOException) {
        dao.institutional("MARKET", market.name, "", window).map { it.toDomain() }
            .ifEmpty { throw error }
    }
    override suspend fun securityInstitutional(code: String, market: MarketCode, window: Int) = try {
        api.securityInstitutional(code, market.name, window).data.also { rows ->
            dao.upsertInstitutional(rows.map { it.toEntity("SECURITY", window) })
        }.map { it.toDomain() }
    } catch (error: IOException) {
        dao.institutional("SECURITY", market.name, code, window).map { it.toDomain() }
            .ifEmpty { throw error }
    }
    override suspend fun securityCredit(code: String, market: MarketCode, window: Int): SecurityCredit {
        return try {
            val response = api.securityCredit(code, market.name, window).data
            dao.upsertCredit(response.margin.map { it.toEntity("MARGIN", code, window, market.name) })
            dao.upsertCredit(response.lending.map { it.toEntity("LENDING", code, window, market.name) })
            SecurityCredit(response.margin.map { it.toDomain() }, response.lending.map { it.toDomain() })
        } catch (error: IOException) {
            val margin = dao.credit("MARGIN", market.name, code, window).map { it.toMarginDomain() }
            val lending = dao.credit("LENDING", market.name, code, window).map { it.toLendingDomain() }
            if (margin.isEmpty() && lending.isEmpty()) throw error
            SecurityCredit(margin, lending)
        }
    }
}

private fun MarketOverviewEnvelopeDto.toDomain(cache: Boolean) = MarketOverview(data.indexes.map { it.toDomain() },
    data.breadth.map { it.toDomain() }, data.institutionalSpot.map { it.toDomain() },
    data.credit.map { it.toDomain() }, data.lending.map { it.toDomain() }, meta.asOf,
    DataStatus.valueOf(meta.dataStatus), cache)
private fun MarketIndexDto.toDomain() = MarketIndex(code, name, MarketCode.valueOf(market), tradeDate,
    open, high, low, close, change, changePercent, turnoverAmount, volume, asOf, DataStatus.valueOf(dataStatus))
private fun MarketBreadthDto.toDomain() = MarketBreadth(MarketCode.valueOf(market), tradeDate, advancers,
    decliners, unchanged, limitUp, limitDown, totalTraded, turnoverAmount, asOf, DataStatus.valueOf(dataStatus))
private fun InstitutionalPointDto.toDomain() = InstitutionalPoint(MarketCode.valueOf(market), securityCode,
    tradeDate, InstitutionType.valueOf(institutionType), dealerSubtype?.let(DealerSubtype::valueOf),
    buy, sell, net, cumulativeNet, consecutiveDirectionDays, asOf, DataStatus.valueOf(dataStatus))
private fun MarginPointDto.toDomain() = MarginPoint(tradeDate, marginBalance, marginBalanceChange,
    shortBalance, shortBalanceChange, shortMarginRatio, asOf, DataStatus.valueOf(dataStatus))
private fun LendingPointDto.toDomain() = LendingPoint(tradeDate, lendingSell, lendingBalance,
    lendingBalanceChange, asOf, DataStatus.valueOf(dataStatus))
private fun MarketIndexDto.toEntity() = MarketIndexEntity(code, name, market, tradeDate, open, high, low,
    close, change, changePercent, turnoverAmount, volume, asOf, dataStatus)
private fun MarketBreadthDto.toEntity() = MarketBreadthEntity(market, tradeDate, advancers, decliners,
    unchanged, limitUp, limitDown, totalTraded, turnoverAmount, asOf, dataStatus)
private fun InstitutionalPointDto.toEntity(dataset: String, window: Int) = InstitutionalEntity(
    dataset, market, securityCode ?: "", window, tradeDate, institutionType, dealerSubtype ?: "NONE",
    buy, sell, net, cumulativeNet, consecutiveDirectionDays, asOf, dataStatus)
private fun MarginPointDto.toEntity(dataset: String, security: String, window: Int, market: String = "") =
    CreditEntity(dataset, market, security, window, tradeDate, marginBalance, marginBalanceChange,
        shortBalance, shortBalanceChange, shortMarginRatio, asOf, dataStatus)
private fun LendingPointDto.toEntity(dataset: String, security: String, window: Int, market: String = "") =
    CreditEntity(dataset, market, security, window, tradeDate, lendingBalance, lendingBalanceChange,
        lendingSell, null, null, asOf, dataStatus)
private fun MarketIndexEntity.toDomain() = MarketIndex(code, name, MarketCode.valueOf(market), tradeDate,
    open, high, low, close, change, changePercent, turnoverAmount, volume, asOf, DataStatus.STALE)
private fun MarketBreadthEntity.toDomain() = MarketBreadth(MarketCode.valueOf(market), tradeDate, advancers,
    decliners, unchanged, limitUp, limitDown, totalTraded, turnoverAmount, asOf, DataStatus.STALE)
private fun InstitutionalEntity.toDomain() = InstitutionalPoint(MarketCode.valueOf(market),
    security.ifEmpty { null }, tradeDate, InstitutionType.valueOf(institution),
    dealerSubtype.takeUnless { it == "NONE" }?.let(DealerSubtype::valueOf), buy, sell, net,
    cumulativeNet, consecutiveDays, asOf, DataStatus.STALE)
private fun CreditEntity.toMarginDomain() = MarginPoint(tradeDate, balance, change, secondaryBalance,
    secondaryChange, ratio, asOf, DataStatus.STALE)
private fun CreditEntity.toLendingDomain() = LendingPoint(tradeDate, secondaryBalance, balance, change,
    asOf, DataStatus.STALE)
