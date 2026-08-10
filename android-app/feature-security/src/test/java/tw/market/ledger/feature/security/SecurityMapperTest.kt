package tw.market.ledger.feature.security

import org.junit.Assert.assertEquals
import org.junit.Test
import tw.market.ledger.feature.security.data.toDomain
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.SecurityType
import tw.market.ledger.network.SecurityDto

class SecurityMapperTest {
    @Test fun generatedContractStringsMapToDomainEnums() {
        val mapped = SecurityDto(
            id = "00000000-0000-0000-0000-000000000001", code = "1234", name = "測試科技", market = "TWSE",
            securityType = "COMMON_STOCK", status = "ACTIVE", primaryIndustry = null,
            listingDate = null, isActive = true, asOf = "2026-08-06T00:00:00Z",
            receivedAt = "2026-08-06T00:00:01Z", dataStatus = "FINAL",
        ).toDomain()
        assertEquals(SecurityType.COMMON_STOCK, mapped.securityType)
        assertEquals(DataStatus.FINAL, mapped.dataStatus)
        assertEquals("470.10", java.math.BigDecimal("470.10").toPlainString())
    }
}
