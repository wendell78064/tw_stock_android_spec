package tw.market.ledger.feature.security

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import tw.market.ledger.feature.security.domain.DetailOutcome
import tw.market.ledger.feature.security.domain.GetSecurityUseCase
import tw.market.ledger.feature.security.domain.SearchOutcome
import tw.market.ledger.feature.security.domain.SecurityRepository
import tw.market.ledger.feature.security.presentation.SecurityDetailUiState
import tw.market.ledger.feature.security.presentation.SecurityDetailViewModel
import tw.market.ledger.model.AnalysisPrompt
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.RealtimeDataStatus
import tw.market.ledger.model.RealtimeQuote
import tw.market.ledger.network.RealtimeQuoteType
import tw.market.ledger.network.RealtimeSubscriptionClient
import tw.market.ledger.network.RealtimeSubscriptionManager

@OptIn(ExperimentalCoroutinesApi::class)
class SecurityDetailViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private class FakeClient : RealtimeSubscriptionClient {
        data class Call(
            val action: String,
            val market: String,
            val code: String,
            val quoteTypes: Set<RealtimeQuoteType>,
        )

        private val mutableQuotes = MutableSharedFlow<RealtimeQuote>(replay = 1)
        override val quotesFlow: SharedFlow<RealtimeQuote> = mutableQuotes
        val calls = mutableListOf<Call>()

        override fun connect() = Unit

        override fun subscribe(
            market: String,
            code: String,
            quoteTypes: Set<RealtimeQuoteType>,
        ) {
            calls += Call("subscribe", market, code, quoteTypes)
        }

        override fun unsubscribe(
            market: String,
            code: String,
            quoteTypes: Set<RealtimeQuoteType>,
        ) {
            calls += Call("unsubscribe", market, code, quoteTypes)
        }

        fun emit(quote: RealtimeQuote) {
            mutableQuotes.tryEmit(quote)
        }
    }

    private class FakeRepository(private val fromCache: Boolean = false) : SecurityRepository {
        override suspend fun search(
            query: String,
            market: MarketCode?,
            limit: Int,
        ): SearchOutcome = error("not used")

        override suspend fun detail(code: String, market: MarketCode): DetailOutcome =
            DetailOutcome(security(code), fromCache)

        override suspend fun analysisPrompt(code: String, market: MarketCode): AnalysisPrompt =
            error("not used")
    }

    @Test
    fun `current view acquires both types deduplicates changes and releases`() =
        runTest(dispatcher) {
            val client = FakeClient()
            val managerJob = Job()
            val manager = RealtimeSubscriptionManager(
                client,
                CoroutineScope(dispatcher + managerJob),
            )
            val viewModel = SecurityDetailViewModel(
                GetSecurityUseCase(FakeRepository()),
                manager,
            )
            val both = setOf(RealtimeQuoteType.TICK, RealtimeQuoteType.BID_ASK)

            viewModel.load("2330", MarketCode.TWSE)
            advanceUntilIdle()
            assertEquals(listOf(FakeClient.Call("subscribe", "TWSE", "2330", both)), client.calls)

            viewModel.load("2330", MarketCode.TWSE)
            advanceUntilIdle()
            assertEquals(1, client.calls.size)

            client.emit(quote("2330", RealtimeDataStatus.STALE))
            advanceUntilIdle()
            assertEquals(RealtimeDataStatus.STALE, viewModel.realtimeQuote.value?.dataStatus)
            assertTrue(viewModel.uiState.value is SecurityDetailUiState.Success)

            viewModel.load("2454", MarketCode.TWSE)
            assertEquals(FakeClient.Call("unsubscribe", "TWSE", "2330", both), client.calls[1])
            assertEquals(FakeClient.Call("subscribe", "TWSE", "2454", both), client.calls[2])
            assertNull(viewModel.realtimeQuote.value)

            viewModel.leave("2454", MarketCode.TWSE)
            assertEquals(FakeClient.Call("unsubscribe", "TWSE", "2454", both), client.calls.last())
            managerJob.cancel()
        }

    @Test
    fun `realtime absence preserves stale daily detail without zero fill`() =
        runTest(dispatcher) {
            val client = FakeClient()
            val managerJob = Job()
            val viewModel = SecurityDetailViewModel(
                GetSecurityUseCase(FakeRepository(fromCache = true)),
                RealtimeSubscriptionManager(
                    client,
                    CoroutineScope(dispatcher + managerJob),
                ),
            )

            viewModel.load("2330", MarketCode.TWSE)
            advanceUntilIdle()

            assertTrue(viewModel.uiState.value is SecurityDetailUiState.Stale)
            assertNull(viewModel.realtimeQuote.value)
            viewModel.leave("2330", MarketCode.TWSE)
            managerJob.cancel()
        }

    private fun quote(code: String, status: RealtimeDataStatus) = RealtimeQuote(
        securityId = "sec_$code",
        marketId = "TWSE",
        code = code,
        exchangeTimestamp = "2026-08-24T03:00:00Z",
        receivedAt = "2026-08-24T03:00:00.100Z",
        lastPrice = "100.0",
        changePercent = null,
        dataStatus = status,
    )
}
