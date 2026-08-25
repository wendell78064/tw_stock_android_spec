package tw.market.ledger.feature.portfolio

import java.io.IOException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.test.*
import org.junit.*
import tw.market.ledger.feature.portfolio.domain.*
import tw.market.ledger.feature.portfolio.presentation.*
import tw.market.ledger.model.*
import tw.market.ledger.network.*

@OptIn(ExperimentalCoroutinesApi::class)
class PortfolioViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setup() = Dispatchers.setMain(dispatcher)
    @After fun close() = Dispatchers.resetMain()

    @Test fun loadingSuccessSortAndRefreshAfterBuySell() = runTest(dispatcher) {
        val repository = FakeRepository()
        val viewModel = PortfolioViewModel(repository, manager(backgroundScope))
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
            val viewModel = PortfolioViewModel(
                FakeRepository(value, fail),
                manager(this@runTest.backgroundScope),
            )
            advanceUntilIdle()
            return viewModel.state.value
        }
        Assert.assertTrue(state(dashboard.copy(holdings=emptyList())) is PortfolioUiState.Empty)
        Assert.assertTrue(state(fail=true) is PortfolioUiState.Error)
        Assert.assertTrue(state(dashboard.copy(summary=summary.copy(fromCache=true))) is PortfolioUiState.Offline)
        Assert.assertTrue(state(dashboard.copy(summary=summary.copy(dataStatus=DataStatus.STALE))) is PortfolioUiState.Stale)
        Assert.assertTrue(state(dashboard.copy(summary=summary.copy(dataStatus=DataStatus.PARTIAL))) is PortfolioUiState.Partial)
    }

    @Test fun activeHoldingsDriveP0TickAndLiveQuoteWithoutZeroFallback() = runTest(dispatcher) {
        val client = FakeRealtimeClient()
        val subscriptions = manager(backgroundScope, client, enabled = true)
        val repository = FakeRepository()
        val viewModel = PortfolioViewModel(repository, subscriptions)
        advanceUntilIdle()
        runCurrent()

        Assert.assertEquals(
            listOf(FakeRealtimeClient.Call("subscribe", "TWSE", "2330", setOf(RealtimeQuoteType.TICK))),
            client.calls,
        )
        client.emit(
            RealtimeQuote(
                securityId = "sec_2330",
                marketId = "TWSE",
                code = "2330",
                exchangeTimestamp = "2026-08-25T01:30:00Z",
                receivedAt = "2026-08-25T01:30:00Z",
                lastPrice = "20",
                dataStatus = RealtimeDataStatus.LIVE,
            )
        )
        runCurrent()
        val live = (viewModel.state.value as PortfolioUiState.Success).dashboard
        Assert.assertEquals("20", live.holdings.single().latestPrice)
        Assert.assertEquals("20000", live.holdings.single().marketValue)
        Assert.assertEquals(DataStatus.LIVE, live.holdings.single().priceDataStatus)

        repository.value = dashboard.copy(holdings = emptyList())
        viewModel.refresh()
        advanceUntilIdle()
        Assert.assertEquals("unsubscribe", client.calls.last().action)
        Assert.assertEquals(setOf(RealtimeQuoteType.TICK), client.calls.last().quoteTypes)
    }

    @Test fun cachedPortfolioDoesNotCreateUnconfirmedMembership() = runTest(dispatcher) {
        val client = FakeRealtimeClient()
        val cached = dashboard.copy(summary = summary.copy(fromCache = true))
        val viewModel = PortfolioViewModel(
            FakeRepository(cached),
            manager(backgroundScope, client, enabled = true),
        )
        advanceUntilIdle()
        Assert.assertTrue(viewModel.state.value is PortfolioUiState.Offline)
        Assert.assertTrue(client.calls.isEmpty())
    }

    private fun manager(
        scope: CoroutineScope,
        client: FakeRealtimeClient = FakeRealtimeClient(),
        enabled: Boolean = false,
    ) = RealtimeSubscriptionManager(
        client,
        scope,
        portfolioRealtimeEnabled = enabled,
    )
}

private class FakeRepository(var value: PortfolioDashboard? = dashboard,
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

private class FakeRealtimeClient : RealtimeSubscriptionClient {
    data class Call(
        val action: String,
        val market: String,
        val code: String,
        val quoteTypes: Set<RealtimeQuoteType>,
    )

    private val quotes = MutableSharedFlow<RealtimeQuote>(replay = 1, extraBufferCapacity = 4)
    override val quotesFlow: SharedFlow<RealtimeQuote> = quotes
    val calls = mutableListOf<Call>()

    override fun connect() = Unit

    override fun subscribe(market: String, code: String, quoteTypes: Set<RealtimeQuoteType>) {
        calls += Call("subscribe", market, code, quoteTypes)
    }

    override fun unsubscribe(market: String, code: String, quoteTypes: Set<RealtimeQuoteType>) {
        calls += Call("unsubscribe", market, code, quoteTypes)
    }

    fun emit(quote: RealtimeQuote) {
        quotes.tryEmit(quote)
    }
}
