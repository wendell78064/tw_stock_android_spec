package tw.market.ledger.feature.security

import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security
import tw.market.ledger.model.SecurityStatus
import tw.market.ledger.model.SecurityType

fun security(code: String = "1234") = Security(
    id = "00000000-0000-0000-0000-000000000001",
    code = code,
    name = "測試科技",
    market = MarketCode.TWSE,
    securityType = SecurityType.COMMON_STOCK,
    status = SecurityStatus.ACTIVE,
    primaryIndustry = "測試科技業",
    listingDate = "2023-01-02",
    isActive = true,
    asOf = "2026-08-06T00:00:00Z",
    receivedAt = "2026-08-06T00:00:01Z",
    dataStatus = DataStatus.FINAL,
)

