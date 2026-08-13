package tw.market.ledger.feature.comparison

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import tw.market.ledger.model.MarketCode

@OptIn(ExperimentalCoroutinesApi::class)
class ComparisonTests {
    private val testDispatcher = StandardTestDispatcher()
    private lateinit var fakeApi: FakeComparisonApi

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        fakeApi = FakeComparisonApi()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testSelectionManagerLimitsAndDuplicates() {
        val manager = ComparisonSelectionManager()
        val s1 = SecurityTarget("2330", MarketCode.TWSE)
        val s2 = SecurityTarget("2317", MarketCode.TWSE)
        val s3 = SecurityTarget("2454", MarketCode.TWSE)
        val s4 = SecurityTarget("2308", MarketCode.TWSE)
        val s5 = SecurityTarget("2382", MarketCode.TWSE)
        val s6 = SecurityTarget("2303", MarketCode.TWSE)

        assertTrue(manager.addTarget(s1))
        assertFalse(manager.addTarget(s1)) // Duplicate
        assertTrue(manager.addTarget(s2))
        assertTrue(manager.addTarget(s3))
        assertTrue(manager.addTarget(s4))
        assertTrue(manager.addTarget(s5))
        assertFalse(manager.addTarget(s6)) // Exceed 5

        assertEquals(5, manager.targets.value.size)
        manager.removeTarget("2330", MarketCode.TWSE)
        assertEquals(4, manager.targets.value.size)
    }

    @Test
    fun testViewModelComparisonFlow() = runTest {
        val vm = ComparisonViewModel(fakeApi)
        val t1 = SecurityTarget("2330", MarketCode.TWSE)
        val t2 = SecurityTarget("2317", MarketCode.TWSE)
        vm.setTargets(listOf(t1, t2))
        testDispatcher.scheduler.advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals(2, state.summaries.size)
        assertEquals("2330", state.summaries[0].code)
        assertEquals(1, state.signals.size)
        assertEquals("台積電 近期報酬表現優於 鴻海", state.signals[0].headline)
    }
}
