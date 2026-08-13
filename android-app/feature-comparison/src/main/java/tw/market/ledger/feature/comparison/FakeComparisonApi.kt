package tw.market.ledger.feature.comparison

import retrofit2.Response
import tw.market.ledger.network.ComparisonApi
import tw.market.ledger.network.ComparisonEnvelopeDto
import tw.market.ledger.network.ComparisonResultDto
import tw.market.ledger.network.ComparisonSecuritySummaryDto
import tw.market.ledger.network.MetaDto
import tw.market.ledger.network.NormalizedPointDto
import tw.market.ledger.network.ObjectiveSignalDto
import tw.market.ledger.network.RunComparisonInputDto

class FakeComparisonApi : ComparisonApi {
    override suspend fun runComparison(input: RunComparisonInputDto): Response<ComparisonEnvelopeDto> {
        val meta = MetaDto("2026-08-11T00:00:00Z", "2026-08-11T00:00:00Z", "FINAL", "TEST")
        val s1 = ComparisonSecuritySummaryDto(
            security_id = "sec1",
            code = "2330",
            name = "台積電",
            market = "TWSE",
            latest_close = "950.00",
            return_20d = "12.50",
            rsi14 = "65.00",
            data_status = "FINAL"
        )
        val s2 = ComparisonSecuritySummaryDto(
            security_id = "sec2",
            code = "2317",
            name = "鴻海",
            market = "TWSE",
            latest_close = "200.00",
            return_20d = "4.20",
            rsi14 = "48.00",
            data_status = "FINAL"
        )
        val norm = listOf(
            NormalizedPointDto("2026-08-10", mapOf("2330" to "100.00", "2317" to "100.00")),
            NormalizedPointDto("2026-08-11", mapOf("2330" to "102.50", "2317" to "101.00"))
        )
        val sig = listOf(
            ObjectiveSignalDto(
                signal_type = "PRICE_OUTPERFORMANCE",
                subject_code = "2330",
                comparator_code = "2317",
                headline = "台積電 近期報酬表現優於 鴻海",
                details = "2330 報酬率為 12.50%，較 2317 (4.20%) 高出 8.30 個百分點"
            )
        )
        val res = ComparisonResultDto(
            window = input.window,
            requested_start = "2026-07-11",
            effective_start = "2026-08-10",
            effective_end = "2026-08-11",
            securities = listOf(s1, s2),
            normalized_series = norm,
            objective_signals = sig,
            coverage = "1.00"
        )
        return Response.success(ComparisonEnvelopeDto(res, meta))
    }
}
