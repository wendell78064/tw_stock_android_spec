package tw.market.ledger.feature.industry.data

import tw.market.ledger.database.IndustryEntity
import tw.market.ledger.database.TaxonomyDao
import tw.market.ledger.database.TaxonomyMemberEntity
import tw.market.ledger.database.ThemeEntity
import tw.market.ledger.feature.industry.domain.IndustryRepository
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.Industry
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.SecurityType
import tw.market.ledger.model.TaxonomyDetail
import tw.market.ledger.model.TaxonomyMember
import tw.market.ledger.model.Theme
import tw.market.ledger.network.IndustryApi
import javax.inject.Inject

class IndustryRepositoryImpl @Inject constructor(
    private val api: IndustryApi,
    private val dao: TaxonomyDao,
) : IndustryRepository {

    override suspend fun getIndustries(): Result<Pair<List<Industry>, Boolean>> {
        return try {
            val response = api.getIndustries()
            val industries = response.data.map { dto ->
                Industry(
                    id = dto.id,
                    code = dto.code,
                    name = dto.name,
                    classificationSource = dto.classificationSource,
                    memberCount = dto.memberCount,
                )
            }
            dao.insertIndustries(industries.map { ind ->
                IndustryEntity(
                    id = ind.id,
                    code = ind.code,
                    name = ind.name,
                    classificationSource = ind.classificationSource,
                    memberCount = ind.memberCount,
                )
            })
            Result.success(Pair(industries, false))
        } catch (e: Exception) {
            val cached = dao.getIndustries()
            if (cached.isNotEmpty()) {
                val industries = cached.map { entity ->
                    Industry(
                        id = entity.id,
                        code = entity.code,
                        name = entity.name,
                        classificationSource = entity.classificationSource,
                        memberCount = entity.memberCount,
                    )
                }
                Result.success(Pair(industries, true))
            } else {
                Result.failure(e)
            }
        }
    }

    override suspend fun getIndustryDetail(id: String): Result<TaxonomyDetail<Industry>> {
        return try {
            val indDto = api.getIndustry(id).data
            val secEnvelope = api.getIndustrySecurities(id)
            val industry = Industry(
                id = indDto.id,
                code = indDto.code,
                name = indDto.name,
                classificationSource = indDto.classificationSource,
                memberCount = indDto.memberCount,
            )
            val members = secEnvelope.data.map { mem ->
                TaxonomyMember(
                    securityId = mem.securityId,
                    code = mem.code,
                    name = mem.name,
                    market = MarketCode.valueOf(mem.market),
                    securityType = SecurityType.valueOf(mem.securityType),
                    isActive = mem.isActive,
                    close = mem.close,
                    change = mem.change,
                    changePercent = mem.changePercent,
                    asOf = mem.asOf,
                    dataStatus = DataStatus.valueOf(mem.dataStatus),
                )
            }
            dao.insertIndustry(
                IndustryEntity(
                    industry.id,
                    industry.code,
                    industry.name,
                    industry.classificationSource,
                    industry.memberCount,
                )
            )
            dao.clearTaxonomyMembers(id)
            dao.insertTaxonomyMembers(members.map { mem ->
                TaxonomyMemberEntity(
                    taxonomyId = id,
                    securityId = mem.securityId,
                    code = mem.code,
                    name = mem.name,
                    market = mem.market.name,
                    securityType = mem.securityType.name,
                    isActive = mem.isActive,
                    close = mem.close,
                    change = mem.change,
                    changePercent = mem.changePercent,
                    asOf = mem.asOf,
                    dataStatus = mem.dataStatus.name,
                )
            })
            Result.success(
                TaxonomyDetail(
                    taxonomy = industry,
                    members = members,
                    asOf = secEnvelope.meta.asOf,
                    dataStatus = DataStatus.valueOf(secEnvelope.meta.dataStatus),
                    isStale = false,
                )
            )
        } catch (e: Exception) {
            val cachedInd = dao.getIndustry(id)
            val cachedMembers = dao.getTaxonomyMembers(id)
            if (cachedInd != null) {
                val industry = Industry(
                    cachedInd.id,
                    cachedInd.code,
                    cachedInd.name,
                    cachedInd.classificationSource,
                    cachedInd.memberCount,
                )
                val members = cachedMembers.map { entity ->
                    TaxonomyMember(
                        securityId = entity.securityId,
                        code = entity.code,
                        name = entity.name,
                        market = MarketCode.valueOf(entity.market),
                        securityType = SecurityType.valueOf(entity.securityType),
                        isActive = entity.isActive,
                        close = entity.close,
                        change = entity.change,
                        changePercent = entity.changePercent,
                        asOf = entity.asOf,
                        dataStatus = DataStatus.STALE,
                    )
                }
                Result.success(
                    TaxonomyDetail(
                        taxonomy = industry,
                        members = members,
                        asOf = members.firstOrNull()?.asOf ?: "",
                        dataStatus = DataStatus.STALE,
                        isStale = true,
                    )
                )
            } else {
                Result.failure(e)
            }
        }
    }

    override suspend fun getThemes(): Result<Pair<List<Theme>, Boolean>> {
        return try {
            val response = api.getThemes()
            val themes = response.data.map { dto ->
                Theme(
                    id = dto.id,
                    code = dto.code,
                    name = dto.name,
                    description = dto.description,
                    classificationType = dto.classificationType,
                    memberCount = dto.memberCount,
                    createdAt = dto.createdAt,
                    updatedAt = dto.updatedAt,
                )
            }
            dao.insertThemes(themes.map { t ->
                ThemeEntity(
                    id = t.id,
                    code = t.code,
                    name = t.name,
                    description = t.description,
                    classificationType = t.classificationType,
                    memberCount = t.memberCount,
                    createdAt = t.createdAt,
                    updatedAt = t.updatedAt,
                )
            })
            Result.success(Pair(themes, false))
        } catch (e: Exception) {
            val cached = dao.getThemes()
            if (cached.isNotEmpty()) {
                val themes = cached.map { entity ->
                    Theme(
                        id = entity.id,
                        code = entity.code,
                        name = entity.name,
                        description = entity.description,
                        classificationType = entity.classificationType,
                        memberCount = entity.memberCount,
                        createdAt = entity.createdAt,
                        updatedAt = entity.updatedAt,
                    )
                }
                Result.success(Pair(themes, true))
            } else {
                Result.failure(e)
            }
        }
    }

    override suspend fun getThemeDetail(id: String): Result<TaxonomyDetail<Theme>> {
        return try {
            val themeDto = api.getTheme(id).data
            val secEnvelope = api.getThemeSecurities(id)
            val theme = Theme(
                id = themeDto.id,
                code = themeDto.code,
                name = themeDto.name,
                description = themeDto.description,
                classificationType = themeDto.classificationType,
                memberCount = themeDto.memberCount,
                createdAt = themeDto.createdAt,
                updatedAt = themeDto.updatedAt,
            )
            val members = secEnvelope.data.map { mem ->
                TaxonomyMember(
                    securityId = mem.securityId,
                    code = mem.code,
                    name = mem.name,
                    market = MarketCode.valueOf(mem.market),
                    securityType = SecurityType.valueOf(mem.securityType),
                    isActive = mem.isActive,
                    close = mem.close,
                    change = mem.change,
                    changePercent = mem.changePercent,
                    asOf = mem.asOf,
                    dataStatus = DataStatus.valueOf(mem.dataStatus),
                )
            }
            dao.insertTheme(
                ThemeEntity(
                    theme.id,
                    theme.code,
                    theme.name,
                    theme.description,
                    theme.classificationType,
                    theme.memberCount,
                    theme.createdAt,
                    theme.updatedAt,
                )
            )
            dao.clearTaxonomyMembers(id)
            dao.insertTaxonomyMembers(members.map { mem ->
                TaxonomyMemberEntity(
                    taxonomyId = id,
                    securityId = mem.securityId,
                    code = mem.code,
                    name = mem.name,
                    market = mem.market.name,
                    securityType = mem.securityType.name,
                    isActive = mem.isActive,
                    close = mem.close,
                    change = mem.change,
                    changePercent = mem.changePercent,
                    asOf = mem.asOf,
                    dataStatus = mem.dataStatus.name,
                )
            })
            Result.success(
                TaxonomyDetail(
                    taxonomy = theme,
                    members = members,
                    asOf = secEnvelope.meta.asOf,
                    dataStatus = DataStatus.valueOf(secEnvelope.meta.dataStatus),
                    isStale = false,
                )
            )
        } catch (e: Exception) {
            val cachedTheme = dao.getTheme(id)
            val cachedMembers = dao.getTaxonomyMembers(id)
            if (cachedTheme != null) {
                val theme = Theme(
                    cachedTheme.id,
                    cachedTheme.code,
                    cachedTheme.name,
                    cachedTheme.description,
                    cachedTheme.classificationType,
                    cachedTheme.memberCount,
                    cachedTheme.createdAt,
                    cachedTheme.updatedAt,
                )
                val members = cachedMembers.map { entity ->
                    TaxonomyMember(
                        securityId = entity.securityId,
                        code = entity.code,
                        name = entity.name,
                        market = MarketCode.valueOf(entity.market),
                        securityType = SecurityType.valueOf(entity.securityType),
                        isActive = entity.isActive,
                        close = entity.close,
                        change = entity.change,
                        changePercent = entity.changePercent,
                        asOf = entity.asOf,
                        dataStatus = DataStatus.STALE,
                    )
                }
                Result.success(
                    TaxonomyDetail(
                        taxonomy = theme,
                        members = members,
                        asOf = members.firstOrNull()?.asOf ?: "",
                        dataStatus = DataStatus.STALE,
                        isStale = true,
                    )
                )
            } else {
                Result.failure(e)
            }
        }
    }
}
