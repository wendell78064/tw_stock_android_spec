package tw.market.ledger.feature.security

import java.io.IOException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import tw.market.ledger.database.SecurityDao
import tw.market.ledger.database.SecurityEntity
import tw.market.ledger.feature.security.data.DefaultSecurityRepository
import tw.market.ledger.feature.security.data.toEntity
import tw.market.ledger.model.DataStatus
import tw.market.ledger.network.MetaDto
import tw.market.ledger.network.SecurityApi
import tw.market.ledger.network.SecurityDto
import tw.market.ledger.network.SecurityEnvelopeDto
import tw.market.ledger.network.SecuritySearchEnvelopeDto

class SecurityRepositoryTest {
    @Test fun remoteResultsAreMappedAndCached() = runTest {
        val dao = FakeDao()
        val repository = DefaultSecurityRepository(FakeApi(), dao)
        val outcome = repository.search("12", null, 20)
        assertEquals("1234", outcome.result.securities.single().code)
        assertEquals(1, dao.items.size)
    }

    @Test fun networkFailureReturnsStaleCache() = runTest {
        val dao = FakeDao(mutableListOf(security().toEntity()))
        val repository = DefaultSecurityRepository(FakeApi(fail = true), dao)
        val outcome = repository.search("12", null, 20)
        assertEquals(true, outcome.fromCache)
        assertEquals(DataStatus.STALE, outcome.result.dataStatus)
    }
}

private class FakeApi(private val fail: Boolean = false) : SecurityApi {
    private val dto = SecurityDto(
        "00000000-0000-0000-0000-000000000001", "1234", "測試科技", "TWSE", "COMMON_STOCK", "ACTIVE", "測試科技業",
        "2023-01-02", true, "2026-08-06T00:00:00Z", "2026-08-06T00:00:01Z", "FINAL",
    )
    private val meta = MetaDto("2026-08-06T00:00:00Z", "2026-08-06T00:00:01Z", "FINAL", "FAKE")
    override suspend fun search(query: String, market: String?, type: String, limit: Int): SecuritySearchEnvelopeDto {
        if (fail) throw IOException("offline")
        return SecuritySearchEnvelopeDto(listOf(dto), meta)
    }
    override suspend fun detail(code: String, market: String): SecurityEnvelopeDto = SecurityEnvelopeDto(dto, meta)
    override suspend fun analysisPrompt(code: String, market: String): tw.market.ledger.network.AnalysisPromptEnvelopeDto {
        val promptDto = tw.market.ledger.network.AnalysisPromptDto(
            security = dto,
            asOf = "2026-08-06T00:00:00Z",
            generatedAt = "2026-08-06T00:00:05Z",
            prompt = "PROMPT",
            characterCount = 6,
            dataStatus = "FINAL",
            portfolioIncluded = false,
        )
        return tw.market.ledger.network.AnalysisPromptEnvelopeDto(promptDto, meta)
    }
}


private class FakeDao(val items: MutableList<SecurityEntity> = mutableListOf()) : SecurityDao {
    override suspend fun upsert(items: List<SecurityEntity>) { this.items.clear(); this.items.addAll(items) }
    override suspend fun search(query: String, prefix: String, contains: String, market: String?, limit: Int) =
        items.filter { it.code.startsWith(query) || it.name.contains(query) }.take(limit)
    override suspend fun detail(code: String, market: String) = items.firstOrNull { it.code == code && it.market == market }
}
