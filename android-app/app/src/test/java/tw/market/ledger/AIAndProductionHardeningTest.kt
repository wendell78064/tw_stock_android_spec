package tw.market.ledger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.market.ledger.network.AIAnalyzeRequest
import tw.market.ledger.network.AnalysisStatementDto
import tw.market.ledger.network.RegisterPushTokenRequestDto
import tw.market.ledger.network.StructuredAIAnalysisResultDto
import tw.market.ledger.ui.AIAnalysisUiModel
import tw.market.ledger.ui.AnalysisStatementUiModel

class AIAndProductionHardeningTest {

    @Test
    fun testAIAnalysisDtoMapping() {
        val dto = StructuredAIAnalysisResultDto(
            summary = "台股大盤處於整理階段",
            statements = listOf(
                AnalysisStatementDto(type = "FACT", text = "TAIEX 22500.50", category = "MARKET"),
                AnalysisStatementDto(type = "INFERENCE", text = "籌碼面相對集中", category = "MARKET")
            ),
            risks = listOf("國際股市波動加劇"),
            data_caveats = listOf("缺少三大法人期貨淨部位"),
            generated_at = "2026-08-14T06:00:00Z",
            provider = "FAKE",
            model = "fake-twml-ai-v1",
            prompt_version = "twml-ai-grounding-v1",
            grounding_as_of = "2026-08-14T05:30:00Z",
            cache_hit = true
        )

        val uiModel = AIAnalysisUiModel(
            summary = dto.summary,
            statements = dto.statements.map { AnalysisStatementUiModel(it.type, it.text, it.category) },
            risks = dto.risks,
            dataCaveats = dto.data_caveats,
            generatedAt = dto.generated_at,
            provider = dto.provider,
            model = dto.model,
            groundingAsOf = dto.grounding_as_of,
            cacheHit = dto.cache_hit
        )

        assertEquals("台股大盤處於整理階段", uiModel.summary)
        assertEquals(2, uiModel.statements.size)
        assertEquals("FACT", uiModel.statements[0].type)
        assertEquals("INFERENCE", uiModel.statements[1].type)
        assertEquals("FAKE", uiModel.provider)
        assertTrue(uiModel.cacheHit)
    }

    @Test
    fun testPushRegistrationPayload() {
        val reg = RegisterPushTokenRequestDto(
            device_public_id = "device-pixel-8",
            push_token = "fcm_token_xyz123",
            platform = "ANDROID"
        )
        assertEquals("device-pixel-8", reg.device_public_id)
        assertEquals("fcm_token_xyz123", reg.push_token)
        assertEquals("ANDROID", reg.platform)
    }

    @Test
    fun testAIAnalysisRequestSerialization() {
        val req = AIAnalyzeRequest(
            analysis_type = "MARKET_SUMMARY",
            target_id = null,
            comparison_ids = null,
            screener_expression = null
        )
        assertEquals("MARKET_SUMMARY", req.analysis_type)
    }
}
