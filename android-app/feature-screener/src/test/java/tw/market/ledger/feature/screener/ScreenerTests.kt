package tw.market.ledger.feature.screener

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import retrofit2.Response
import tw.market.ledger.database.ScreenerDao
import tw.market.ledger.database.SavedScreenerEntity
import tw.market.ledger.database.ScreenerResultEntity
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.ScreenerExpression
import tw.market.ledger.network.CreateSavedScreenerInputDto
import tw.market.ledger.network.MetaDto
import tw.market.ledger.network.RunScreenerInputDto
import tw.market.ledger.network.SavedScreenerDto
import tw.market.ledger.network.SavedScreenerEnvelopeDto
import tw.market.ledger.network.SavedScreenerListEnvelopeDto
import tw.market.ledger.network.ScreenerApi
import tw.market.ledger.network.ScreenerFieldMetaDto
import tw.market.ledger.network.ScreenerFieldsEnvelopeDto
import tw.market.ledger.network.ScreenerResultEnvelopeDto
import tw.market.ledger.network.ScreenerResultSecurityDto
import tw.market.ledger.network.UpdateSavedScreenerInputDto

class FakeScreenerDao : ScreenerDao {
    private val savedCache = mutableListOf<SavedScreenerEntity>()
    private val resultCache = mutableListOf<ScreenerResultEntity>()

    override suspend fun getSavedScreeners(): List<SavedScreenerEntity> = savedCache

    override suspend fun upsertSavedScreeners(screeners: List<SavedScreenerEntity>) {
        savedCache.removeAll { s -> screeners.any { it.id == s.id } }
        savedCache.addAll(screeners)
    }

    override suspend fun deleteSavedScreener(id: String) {
        savedCache.removeAll { it.id == id }
    }

    override suspend fun getCachedScreenerResults(): List<ScreenerResultEntity> = resultCache

    override suspend fun replaceCachedScreenerResults(results: List<ScreenerResultEntity>) {
        resultCache.clear()
        resultCache.addAll(results)
    }

    override suspend fun clearScreenerResults() {
        resultCache.clear()
    }
}

class FakeScreenerApi : ScreenerApi {
    var shouldFail = false

    override suspend fun getScreenerFields(): Response<ScreenerFieldsEnvelopeDto> {
        if (shouldFail) return Response.error(500, okhttp3.ResponseBody.create(null, "Error"))
        val field = ScreenerFieldMetaDto(
            field_id = "rsi14",
            label = "RSI(14)",
            category = "TECHNICAL",
            value_type = "NUMERIC",
            allowed_operators = listOf("GT", "LT", "BETWEEN")
        )
        val meta = MetaDto(asOf = "2026-08-11T00:00:00Z", receivedAt = "2026-08-11T00:00:00Z", dataStatus = "FINAL", source = "TEST")
        return Response.success(ScreenerFieldsEnvelopeDto(listOf(field), meta))
    }

    override suspend fun runScreener(input: RunScreenerInputDto): Response<ScreenerResultEnvelopeDto> {
        if (shouldFail) return Response.error(500, okhttp3.ResponseBody.create(null, "Error"))
        val sec = ScreenerResultSecurityDto(
            security_id = UUID.randomUUID().toString(),
            code = "2330",
            name = "台積電",
            market = "TWSE",
            industry_name = "半導體",
            close = "950.00",
            return_pct = "2.50",
            matched_conditions = listOf("PASS RSI14 LT 30"),
            data_status = "FINAL"
        )
        val meta = MetaDto(asOf = "2026-08-11T00:00:00Z", receivedAt = "2026-08-11T00:00:00Z", dataStatus = "FINAL", source = "TEST")
        return Response.success(ScreenerResultEnvelopeDto(listOf(sec), 1, "2026-08-11", meta))
    }

    override suspend fun listSavedScreeners(): Response<SavedScreenerListEnvelopeDto> {
        if (shouldFail) return Response.error(500, okhttp3.ResponseBody.create(null, "Error"))
        val meta = MetaDto(asOf = "2026-08-11T00:00:00Z", receivedAt = "2026-08-11T00:00:00Z", dataStatus = "FINAL", source = "TEST")
        return Response.success(SavedScreenerListEnvelopeDto(emptyList(), meta))
    }

    override suspend fun createSavedScreener(input: CreateSavedScreenerInputDto): Response<SavedScreenerEnvelopeDto> {
        val dto = SavedScreenerDto(
            id = UUID.randomUUID().toString(),
            name = input.name,
            description = input.description,
            expression = input.expression,
            sort_field = input.sort_field,
            sort_direction = input.sort_direction,
            created_at = "2026-08-11T00:00:00Z",
            updated_at = "2026-08-11T00:00:00Z"
        )
        val meta = MetaDto(asOf = "2026-08-11T00:00:00Z", receivedAt = "2026-08-11T00:00:00Z", dataStatus = "FINAL", source = "TEST")
        return Response.success(SavedScreenerEnvelopeDto(dto, meta))
    }

    override suspend fun getSavedScreener(id: String): Response<SavedScreenerEnvelopeDto> {
        TODO("Not required for unit test")
    }

    override suspend fun updateSavedScreener(id: String, input: UpdateSavedScreenerInputDto): Response<SavedScreenerEnvelopeDto> {
        TODO("Not required for unit test")
    }

    override suspend fun deleteSavedScreener(id: String): Response<Unit> {
        return Response.success(Unit)
    }

    override suspend fun runSavedScreener(id: String, limit: Int, offset: Int): Response<ScreenerResultEnvelopeDto> {
        return runScreener(RunScreenerInputDto(expression = mapOf("type" to "AND")))
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ScreenerTests {
    @get:Rule val composeTestRule = createComposeRule()

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var fakeApi: FakeScreenerApi
    private lateinit var fakeDao: FakeScreenerDao
    private lateinit var repository: ScreenerRepository

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        fakeApi = FakeScreenerApi()
        fakeDao = FakeScreenerDao()
        repository = ScreenerRepository(fakeApi, fakeDao)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testRepositoryRunScreenerSuccess() = runTest {
        val expr = ScreenerExpression("CONDITION", "rsi14", "LT", 30)
        val res = repository.runScreener(expr)
        assertTrue(res.isSuccess)
        val list = res.getOrNull()
        assertNotNull(list)
        assertEquals(1, list?.size)
        assertEquals("2330", list?.first()?.code)
    }

    @Test
    fun testBuilderViewModelAddConditionAndGroup() = runTest {
        val vm = ScreenerBuilderViewModel(repository)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.setScreenerName("測試策略")
        vm.addCondition("rsi14", "LT", 30)
        vm.addSubGroup("OR")

        val state = vm.uiState.value
        assertEquals("測試策略", state.screenerName)
        assertEquals(2, state.currentExpression.children.size)
        assertEquals("CONDITION", state.currentExpression.children[0].type)
        assertEquals("OR", state.currentExpression.children[1].type)

        vm.removeChildNode(1)
        assertEquals(1, vm.uiState.value.currentExpression.children.size)
    }

    @Test
    fun testMainScreenComposeRender() {
        val vm = ScreenerMainViewModel(repository)
        composeTestRule.setContent {
            ScreenerMainScreen(
                viewModel = vm,
                onNavigateToBuilder = {},
                onRunExpression = {}
            )
        }
        testDispatcher.scheduler.advanceUntilIdle()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithTag("btn_new_screener").assertIsDisplayed()
        composeTestRule.onNodeWithTag("preset_item_preset_a").assertIsDisplayed()
    }

    @Test
    fun testResultViewModelRunExpression() = runTest {
        val vm = ScreenerResultViewModel(repository)
        val expr = ScreenerExpression("CONDITION", "close", "GT", 500)
        vm.runExpression(expr)
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(1, vm.uiState.value.results.size)
        assertEquals("2330", vm.uiState.value.results.first().code)
    }

    @Test
    fun testResultScreenComposeRender() {
        val vm = ScreenerResultViewModel(repository)
        val expr = ScreenerExpression("CONDITION", "close", "GT", 500)
        vm.runExpression(expr)
        testDispatcher.scheduler.advanceUntilIdle()

        composeTestRule.setContent {
            ScreenerResultScreen(
                viewModel = vm,
                expression = null
            )
        }
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithTag("result_item_2330", useUnmergedTree = true).assertExists()
        composeTestRule.onNodeWithTag("security_code_2330", useUnmergedTree = true).assertExists()
    }
}
