package tw.market.ledger.feature.security.data

import tw.market.ledger.database.SecurityEntity
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.Security
import tw.market.ledger.model.SecurityStatus
import tw.market.ledger.model.SecurityType
import tw.market.ledger.network.SecurityDto
import tw.market.ledger.generated.model.Security as GeneratedSecurity
import tw.market.ledger.generated.model.SecuritySearchItem as GeneratedSearchItem

fun SecurityDto.toDomain(): Security {
    val themeRefs = themes.map { tw.market.ledger.model.ThemeRef(it.id, it.code, it.name) }
    val statusValue = status
    val domainSec = if (statusValue != null) {
        GeneratedSecurity(
            id = java.util.UUID.fromString(id), code = code, name = name,
            market = tw.market.ledger.generated.model.MarketCode.valueOf(market),
            securityType = tw.market.ledger.generated.model.SecurityType.valueOf(securityType),
            status = tw.market.ledger.generated.model.SecurityStatus.valueOf(statusValue),
            isActive = isActive, asOf = java.time.OffsetDateTime.parse(asOf),
            receivedAt = java.time.OffsetDateTime.parse(receivedAt),
            dataStatus = tw.market.ledger.generated.model.DataStatus.valueOf(dataStatus),
            primaryIndustry = primaryIndustry,
            listingDate = listingDate?.let(java.time.LocalDate::parse),
        ).toDomain()
    } else {
        GeneratedSearchItem(
            id = java.util.UUID.fromString(id), code = code, name = name,
            market = tw.market.ledger.generated.model.MarketCode.valueOf(market),
            securityType = tw.market.ledger.generated.model.SecurityType.valueOf(securityType),
            isActive = isActive, asOf = java.time.OffsetDateTime.parse(asOf),
            receivedAt = java.time.OffsetDateTime.parse(receivedAt),
            dataStatus = tw.market.ledger.generated.model.DataStatus.valueOf(dataStatus),
            primaryIndustry = primaryIndustry,
        ).toDomain()
    }
    return domainSec.copy(themes = themeRefs)
}

fun GeneratedSecurity.toDomain(): Security = Security(
    id.toString(), code, name, MarketCode.valueOf(market.name), SecurityType.valueOf(securityType.name),
    SecurityStatus.valueOf(status.name), primaryIndustry, listingDate?.toString(), isActive,
    asOf.toString(), receivedAt.toString(), DataStatus.valueOf(dataStatus.name),
)

fun GeneratedSearchItem.toDomain(): Security = Security(
    id.toString(), code, name, MarketCode.valueOf(market.name), SecurityType.valueOf(securityType.name),
    if (isActive) SecurityStatus.ACTIVE else SecurityStatus.INACTIVE, primaryIndustry, null, isActive,
    asOf.toString(), receivedAt.toString(), DataStatus.valueOf(dataStatus.name),
)

fun Security.toEntity(): SecurityEntity = SecurityEntity(
    id, market.name, code, name, securityType.name, status.name, primaryIndustry, listingDate,
    isActive, asOf, receivedAt, dataStatus.name,
)

fun SecurityEntity.toDomain(): Security = Security(
    id, code, name, MarketCode.valueOf(market), SecurityType.valueOf(securityType),
    SecurityStatus.valueOf(status), primaryIndustry, listingDate, isActive, asOf, receivedAt,
    DataStatus.valueOf(dataStatus),
)
