package tw.market.ledger.feature.portfolio

import java.io.IOException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test
import tw.market.ledger.database.*
import tw.market.ledger.feature.portfolio.data.DefaultPortfolioRepository
import tw.market.ledger.model.*
import tw.market.ledger.network.*

class PortfolioRepositoryTest {
    @Test fun apiSuccessUpdatesReadCacheAndMutationsUseBackend() = runTest {
        val api = FakeApi(); val dao = FakeDao(); val repository = DefaultPortfolioRepository(api, dao)
        val result = repository.dashboard()
        assertEquals("15000", result.summary.totalMarketValue)
        assertEquals(1, dao.holdingRows.size)
        repository.addTransaction("p1", TransactionDraft("2330", MarketCode.TWSE,
            TransactionSide.BUY, "2026-08-11T09:00:00+08:00", 1000, "10", "0",
            LotType.ROUND_LOT))
        repository.deleteTransaction("p1", "tx1")
        assertEquals(1, api.added); assertEquals(1, api.deleted)
    }

    @Test fun offlineReadsCacheButWritesFail() = runTest {
        val dao = FakeDao().apply {
            summaryRow = PortfolioSummaryEntity("00000000-0000-0000-0000-000000000001",
                "15000", "10000", "5000", "0", "50", 1, "2026-08-10", "STALE",
                "NOT_INCLUDED")
        }
        val repository = DefaultPortfolioRepository(FakeApi(fail=true), dao)
        assertTrue(repository.dashboard().summary.fromCache)
        try { repository.addTransaction("p1", TransactionDraft("2330", null,
            TransactionSide.BUY, "2026-08-11T09:00:00+08:00", 1, "10", "0", LotType.ODD_LOT))
            fail("offline write must fail") } catch (_: IOException) { }
    }
}

private class FakeApi(private val fail: Boolean = false) : PortfolioApi {
    var added = 0; var deleted = 0
    private fun check() { if (fail) throw IOException("offline") }
    override suspend fun portfolios(): PortfolioListEnvelopeDto { check(); return PortfolioListEnvelopeDto(
        listOf(PortfolioDto("p1", "Default", "TWD", true))) }
    override suspend fun summary(id: String): PortfolioSummaryEnvelopeDto { check(); return PortfolioSummaryEnvelopeDto(
        PortfolioSummaryDto("15000", "10000", "5000", "0", "50", 1,
            "2026-08-10", "FINAL", "NOT_INCLUDED")) }
    override suspend fun positions(id: String): PortfolioHoldingListEnvelopeDto { check(); return PortfolioHoldingListEnvelopeDto(
        listOf(PortfolioHoldingDto("2330", "台積電", "TWSE", 1000, "10", "10000", "0",
            "15", "2026-08-10", "FINAL", "15000", "5000", "50", "100"))) }
    override suspend fun transactions(id: String): PortfolioTransactionListEnvelopeDto { check(); return PortfolioTransactionListEnvelopeDto(
        listOf(PortfolioTransactionDto("tx1", id, "2330", "台積電", "TWSE", "BUY",
            "2026-08-01", 1000, "10", "0", "ROUND_LOT"))) }
    override suspend fun addTransaction(id: String, input: TransactionInputDto): PortfolioTransactionEnvelopeDto {
        check(); added++; return transactions(id).data.first().let { PortfolioTransactionEnvelopeDto(it) }
    }
    override suspend fun deleteTransaction(id: String, transactionId: String) { check(); deleted++ }
}

private class FakeDao : PortfolioDao {
    var summaryRow: PortfolioSummaryEntity? = null
    var holdingRows = listOf<PortfolioHoldingEntity>()
    var transactionRows = listOf<PortfolioTransactionEntity>()
    override suspend fun upsertSummary(item: PortfolioSummaryEntity) { summaryRow=item }
    override suspend fun upsertHoldings(items: List<PortfolioHoldingEntity>) { holdingRows=items }
    override suspend fun upsertTransactions(items: List<PortfolioTransactionEntity>) { transactionRows=items }
    override suspend fun clearHoldings(portfolioId: String) { holdingRows=emptyList() }
    override suspend fun clearTransactions(portfolioId: String) { transactionRows=emptyList() }
    override suspend fun summary(portfolioId: String) = summaryRow
    override suspend fun holdings(portfolioId: String) = holdingRows
    override suspend fun transactions(portfolioId: String) = transactionRows
}
