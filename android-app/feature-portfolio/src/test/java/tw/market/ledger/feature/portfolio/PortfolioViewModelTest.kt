package tw.market.ledger.feature.portfolio

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.*
import tw.market.ledger.feature.portfolio.domain.*
import tw.market.ledger.feature.portfolio.presentation.*
import tw.market.ledger.model.*

@OptIn(ExperimentalCoroutinesApi::class)
class PortfolioViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setup() = Dispatchers.setMain(dispatcher)
    @After fun close() = Dispatchers.resetMain()

    @Test fun loadingSuccessSortAndRefreshAfterBuySell() = runTest(dispatcher) {
        val repository = FakeRepository()
        val viewModel = PortfolioViewModel(repository)
        Assert.assertTrue(viewModel.state.value is PortfolioUiState.Loading)
        advanceUntilIdle(); Assert.assertTrue(viewModel.state.value is PortfolioUiState.Success)
        viewModel.setSort(HoldingSort.CODE); Assert.assertEquals(HoldingSort.CODE, viewModel.sort.value)
        val draft = TransactionDraft("2330", MarketCode.TWSE, TransactionSide.BUY,
            "2026-08-11T09:00:00+08:00", 1000, "10", "0", LotType.ROUND_LOT)
        viewModel.add(draft); advanceUntilIdle(); Assert.assertEquals(1, repository.added)
        viewModel.delete("tx1"); advanceUntilIdle(); Assert.assertEquals(1, repository.deleted)
    }

    @Test fun emptyOfflineStaleAndPartialStatesAreExplicit() = runTest(dispatcher) {
        suspend fun state(value: PortfolioDashboard? = dashboard, fail: Boolean = false): PortfolioUiState {
            val viewModel = PortfolioViewModel(FakeRepository(value, fail)); advanceUntilIdle()
            return viewModel.state.value
        }
        Assert.assertTrue(state(dashboard.copy(holdings=emptyList())) is PortfolioUiState.Empty)
        Assert.assertTrue(state(fail=true) is PortfolioUiState.Error)
        Assert.assertTrue(state(dashboard.copy(summary=summary.copy(fromCache=true))) is PortfolioUiState.Offline)
        Assert.assertTrue(state(dashboard.copy(summary=summary.copy(dataStatus=DataStatus.STALE))) is PortfolioUiState.Stale)
        Assert.assertTrue(state(dashboard.copy(summary=summary.copy(dataStatus=DataStatus.PARTIAL))) is PortfolioUiState.Partial)
    }
}

private class FakeRepository(private val value: PortfolioDashboard? = dashboard,
    private val fail: Boolean = false) : PortfolioRepository {
    var added = 0; var deleted = 0
    override suspend fun dashboard(): PortfolioDashboard {
        if (fail) throw IOException("offline"); return requireNotNull(value)
    }
    override suspend fun addTransaction(portfolioId: String, draft: TransactionDraft): PortfolioTransaction {
        added++; return transaction
    }
    override suspend fun deleteTransaction(portfolioId: String, transactionId: String) { deleted++ }
}
