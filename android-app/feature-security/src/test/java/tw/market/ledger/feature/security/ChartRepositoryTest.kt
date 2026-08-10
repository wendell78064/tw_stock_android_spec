package tw.market.ledger.feature.security

import java.io.IOException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.market.ledger.database.CandleEntity
import tw.market.ledger.database.ChartDao
import tw.market.ledger.database.TechnicalEntity
import tw.market.ledger.feature.security.data.DefaultChartRepository
import tw.market.ledger.model.CandleInterval
import tw.market.ledger.model.ChartRange
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.PriceBasis
import tw.market.ledger.network.CandleDto
import tw.market.ledger.network.CandleEnvelopeDto
import tw.market.ledger.network.ChartApi
import tw.market.ledger.network.IndicatorValueDto
import tw.market.ledger.network.MetaDto
import tw.market.ledger.network.TechnicalEnvelopeDto
import tw.market.ledger.network.TechnicalPointDto

class ChartRepositoryTest {
    @Test fun remoteCandlesAndTechnicalsAreMappedAndCached() = runTest {
        val dao = FakeChartDao()
        val outcome = DefaultChartRepository(FakeChartApi(), dao).load(
            "1234", MarketCode.TWSE, ChartRange.ONE_YEAR, CandleInterval.DAY,
            PriceBasis.ADJUSTED, setOf("MA20"),
        )
        assertFalse(outcome.fromCache)
        assertEquals("41.0", outcome.candles.candles.single().close)
        assertEquals("40.5", outcome.technicals.single().indicators.single().value)
        assertEquals(1, dao.candleRows.size)
    }

    @Test fun networkFailureUsesStaleCache() = runTest {
        val dao = FakeChartDao().apply {
            candleRows += CandleEntity("TWSE", "1234", "1Y", "1d", "RAW",
                "2026-08-07T00:00:00+08:00", "40", "42", "39", "41", 1000, null,
                "2026-08-07T00:00:00Z", "FINAL")
        }
        val outcome = DefaultChartRepository(FakeChartApi(true), dao).load(
            "1234", MarketCode.TWSE, ChartRange.ONE_YEAR, CandleInterval.DAY,
            PriceBasis.RAW, emptySet(),
        )
        assertTrue(outcome.fromCache)
        assertEquals(DataStatus.STALE, outcome.candles.dataStatus)
    }
}

private class FakeChartApi(private val fail: Boolean = false) : ChartApi {
    private val meta = MetaDto("2026-08-07T00:00:00Z", "2026-08-07T08:00:00Z", "FINAL", "FAKE")
    override suspend fun candles(code: String, market: String, range: String, interval: String, adjustment: String): CandleEnvelopeDto {
        if (fail) throw IOException("offline")
        return CandleEnvelopeDto(listOf(CandleDto("2026-08-07T00:00:00+08:00", "40.0", "42.0", "39.0", "41.0", 1000, null)), meta, interval, adjustment, "日 K")
    }
    override suspend fun technicals(code: String, market: String, basis: String, indicators: String) =
        TechnicalEnvelopeDto(listOf(TechnicalPointDto("2026-08-07", basis, "v1",
            listOf(IndicatorValueDto("MA20", "40.5")), meta.asOf, "FINAL")), meta)
}

private class FakeChartDao : ChartDao {
    val candleRows = mutableListOf<CandleEntity>()
    val technicalRows = mutableListOf<TechnicalEntity>()
    override suspend fun upsertCandles(items: List<CandleEntity>) { candleRows += items }
    override suspend fun clearCandles(market: String, code: String, range: String, interval: String, adjustment: String) { candleRows.clear() }
    override suspend fun candles(market: String, code: String, range: String, interval: String, adjustment: String) = candleRows.toList()
    override suspend fun upsertTechnicals(items: List<TechnicalEntity>) { technicalRows += items }
    override suspend fun technicals(market: String, code: String, basis: String) = technicalRows.toList()
}
