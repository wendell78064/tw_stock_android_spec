package tw.market.ledger.feature.industry.data

import tw.market.ledger.database.IndustryEntity
import tw.market.ledger.database.TaxonomyDao
import tw.market.ledger.database.TaxonomyLeaderEntity
import tw.market.ledger.database.TaxonomyMemberEntity
import tw.market.ledger.database.TaxonomyStrengthEntity
import tw.market.ledger.database.ThemeEntity
import tw.market.ledger.feature.industry.domain.IndustryRepository
import tw.market.ledger.model.DataStatus
import tw.market.ledger.model.Industry
import tw.market.ledger.model.MarketCode
import tw.market.ledger.model.SecurityType
import tw.market.ledger.model.StrengthComponents
import tw.market.ledger.model.TaxonomyDetail
import tw.market.ledger.model.TaxonomyLeader
import tw.market.ledger.model.TaxonomyMember
import tw.market.ledger.model.TaxonomyStrength
import tw.market.ledger.model.TaxonomyStrengthDetail
import tw.market.ledger.model.Theme
import tw.market.ledger.network.IndustryApi
import tw.market.ledger.network.TaxonomyStrengthDto
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

    override suspend fun getIndustryStrengths(window: Int, sort: String): Result<Pair<List<TaxonomyStrength>, Boolean>> {
        return try {
            val response = api.getIndustryStrengths(window = window, sort = sort)
            val strengths = response.data.map { dtoToDomain(it, false) }
            dao.insertStrengths(strengths.map { domainToEntity(it) })
            Result.success(Pair(strengths, false))
        } catch (e: Exception) {
            val cached = dao.getStrengths(type = "OFFICIAL", window = window)
            if (cached.isNotEmpty()) {
                val strengths = cached.map { entityToDomain(it, isStale = true) }
                Result.success(Pair(strengths, true))
            } else {
                Result.failure(e)
            }
        }
    }

    override suspend fun getThemeStrengths(window: Int, sort: String): Result<Pair<List<TaxonomyStrength>, Boolean>> {
        return try {
            val response = api.getThemeStrengths(window = window, sort = sort)
            val strengths = response.data.map { dtoToDomain(it, false) }
            dao.insertStrengths(strengths.map { domainToEntity(it) })
            Result.success(Pair(strengths, false))
        } catch (e: Exception) {
            val cached = dao.getStrengths(type = "CUSTOM", window = window)
            if (cached.isNotEmpty()) {
                val strengths = cached.map { entityToDomain(it, isStale = true) }
                Result.success(Pair(strengths, true))
            } else {
                Result.failure(e)
            }
        }
    }

    override suspend fun getTaxonomyStrengthDetail(id: String, isIndustry: Boolean, window: Int): Result<TaxonomyStrengthDetail> {
        return try {
            val env = if (isIndustry) api.getIndustryStrengthDetail(id, window) else api.getThemeStrengthDetail(id, window)
            val dto = env.data
            val snap = dtoToDomain(dto.snapshot, false)
            val leaders = dto.leaders.map { l ->
                TaxonomyLeader(
                    securityId = l.securityId,
                    code = l.code,
                    name = l.name,
                    market = MarketCode.valueOf(l.market),
                    returnPct = l.returnPct,
                    latestClose = l.latestClose,
                    foreignNet = l.foreignNet,
                    dataStatus = DataStatus.valueOf(l.dataStatus),
                )
            }
            val laggards = dto.laggards.map { l ->
                TaxonomyLeader(
                    securityId = l.securityId,
                    code = l.code,
                    name = l.name,
                    market = MarketCode.valueOf(l.market),
                    returnPct = l.returnPct,
                    latestClose = l.latestClose,
                    foreignNet = l.foreignNet,
                    dataStatus = DataStatus.valueOf(l.dataStatus),
                )
            }
            dao.insertStrengths(listOf(domainToEntity(snap)))
            dao.clearTaxonomyLeaders(id)
            dao.insertTaxonomyLeaders(leaders.map { leaderToEntity(id, it, isLeader = true) } + laggards.map { leaderToEntity(id, it, isLeader = false) })

            Result.success(TaxonomyStrengthDetail(snapshot = snap, leaders = leaders, laggards = laggards, isStale = false))
        } catch (e: Exception) {
            val cachedSnapEntity = dao.getStrengthDetail(id, window)
            val cachedLeadersEntities = dao.getTaxonomyLeaders(id, isLeader = true)
            val cachedLaggardsEntities = dao.getTaxonomyLeaders(id, isLeader = false)
            if (cachedSnapEntity != null) {
                val snap = entityToDomain(cachedSnapEntity, isStale = true)
                val leaders = cachedLeadersEntities.map { entityToLeader(it) }
                val laggards = cachedLaggardsEntities.map { entityToLeader(it) }
                Result.success(TaxonomyStrengthDetail(snapshot = snap, leaders = leaders, laggards = laggards, isStale = true))
            } else {
                Result.failure(e)
            }
        }
    }

    override suspend fun getTaxonomyStrengthHistory(id: String, isIndustry: Boolean, window: Int, limit: Int): Result<Pair<List<TaxonomyStrength>, Boolean>> {
        return try {
            val env = if (isIndustry) api.getIndustryStrengthHistory(id, window, limit) else api.getThemeStrengthHistory(id, window, limit)
            val history = env.data.map { dtoToDomain(it, false) }
            dao.insertStrengths(history.map { domainToEntity(it) })
            Result.success(Pair(history, false))
        } catch (e: Exception) {
            val cached = dao.getStrengthHistory(id, window, limit)
            if (cached.isNotEmpty()) {
                val history = cached.map { entityToDomain(it, isStale = true) }
                Result.success(Pair(history, true))
            } else {
                Result.failure(e)
            }
        }
    }

    private fun dtoToDomain(dto: TaxonomyStrengthDto, isStale: Boolean): TaxonomyStrength {
        val c = dto.components
        return TaxonomyStrength(
            id = dto.id,
            taxonomyId = dto.taxonomyId,
            taxonomyCode = dto.taxonomyCode,
            taxonomyName = dto.taxonomyName,
            taxonomyType = dto.taxonomyType,
            tradeDate = dto.tradeDate,
            window = dto.window,
            equalWeightReturn = dto.equalWeightReturn,
            marketCapWeightedReturn = dto.marketCapWeightedReturn,
            totalMembers = dto.totalMembers,
            validMembers = dto.validMembers,
            coverageRatio = dto.coverageRatio,
            advancers = dto.advancers,
            decliners = dto.decliners,
            unchanged = dto.unchanged,
            advanceRatio = dto.advanceRatio,
            aboveMa20Pct = dto.aboveMa20Pct,
            aboveMa60Pct = dto.aboveMa60Pct,
            foreignNetAmount = dto.foreignNetAmount,
            investmentTrustNetAmount = dto.investmentTrustNetAmount,
            dealerNetAmount = dto.dealerNetAmount,
            marginBalanceChange = dto.marginBalanceChange,
            shortBalanceChange = dto.shortBalanceChange,
            lendingBalanceChange = dto.lendingBalanceChange,
            turnoverAmount = dto.turnoverAmount,
            turnoverShare = dto.turnoverShare,
            turnoverMomentum = dto.turnoverMomentum,
            components = StrengthComponents(
                momentumScore = c.momentumScore,
                breadthScore = c.breadthScore,
                technicalScore = c.technicalScore,
                institutionalScore = c.institutionalScore,
                turnoverScore = c.turnoverScore,
            ),
            strengthScore = dto.strengthScore,
            componentCoverage = dto.componentCoverage,
            rank = dto.rank,
            algorithmVersion = dto.algorithmVersion,
            dataStatus = DataStatus.valueOf(dto.dataStatus),
            asOf = dto.asOf,
            isStale = isStale,
        )
    }

    private fun domainToEntity(domain: TaxonomyStrength): TaxonomyStrengthEntity {
        val c = domain.components
        return TaxonomyStrengthEntity(
            id = domain.id,
            taxonomyId = domain.taxonomyId,
            taxonomyCode = domain.taxonomyCode,
            taxonomyName = domain.taxonomyName,
            taxonomyType = domain.taxonomyType,
            tradeDate = domain.tradeDate,
            window = domain.window,
            equalWeightReturn = domain.equalWeightReturn,
            marketCapWeightedReturn = domain.marketCapWeightedReturn,
            totalMembers = domain.totalMembers,
            validMembers = domain.validMembers,
            coverageRatio = domain.coverageRatio,
            advancers = domain.advancers,
            decliners = domain.decliners,
            unchanged = domain.unchanged,
            advanceRatio = domain.advanceRatio,
            aboveMa20Pct = domain.aboveMa20Pct,
            aboveMa60Pct = domain.aboveMa60Pct,
            foreignNetAmount = domain.foreignNetAmount,
            investmentTrustNetAmount = domain.investmentTrustNetAmount,
            dealerNetAmount = domain.dealerNetAmount,
            marginBalanceChange = domain.marginBalanceChange,
            shortBalanceChange = domain.shortBalanceChange,
            lendingBalanceChange = domain.lendingBalanceChange,
            turnoverAmount = domain.turnoverAmount,
            turnoverShare = domain.turnoverShare,
            turnoverMomentum = domain.turnoverMomentum,
            momentumScore = c.momentumScore,
            breadthScore = c.breadthScore,
            technicalScore = c.technicalScore,
            institutionalScore = c.institutionalScore,
            turnoverScore = c.turnoverScore,
            strengthScore = domain.strengthScore,
            componentCoverage = domain.componentCoverage,
            rank = domain.rank,
            algorithmVersion = domain.algorithmVersion,
            dataStatus = domain.dataStatus.name,
            asOf = domain.asOf,
        )
    }

    private fun entityToDomain(entity: TaxonomyStrengthEntity, isStale: Boolean): TaxonomyStrength {
        return TaxonomyStrength(
            id = entity.id,
            taxonomyId = entity.taxonomyId,
            taxonomyCode = entity.taxonomyCode,
            taxonomyName = entity.taxonomyName,
            taxonomyType = entity.taxonomyType,
            tradeDate = entity.tradeDate,
            window = entity.window,
            equalWeightReturn = entity.equalWeightReturn,
            marketCapWeightedReturn = entity.marketCapWeightedReturn,
            totalMembers = entity.totalMembers,
            validMembers = entity.validMembers,
            coverageRatio = entity.coverageRatio,
            advancers = entity.advancers,
            decliners = entity.decliners,
            unchanged = entity.unchanged,
            advanceRatio = entity.advanceRatio,
            aboveMa20Pct = entity.aboveMa20Pct,
            aboveMa60Pct = entity.aboveMa60Pct,
            foreignNetAmount = entity.foreignNetAmount,
            investmentTrustNetAmount = entity.investmentTrustNetAmount,
            dealerNetAmount = entity.dealerNetAmount,
            marginBalanceChange = entity.marginBalanceChange,
            shortBalanceChange = entity.shortBalanceChange,
            lendingBalanceChange = entity.lendingBalanceChange,
            turnoverAmount = entity.turnoverAmount,
            turnoverShare = entity.turnoverShare,
            turnoverMomentum = entity.turnoverMomentum,
            components = StrengthComponents(
                momentumScore = entity.momentumScore,
                breadthScore = entity.breadthScore,
                technicalScore = entity.technicalScore,
                institutionalScore = entity.institutionalScore,
                turnoverScore = entity.turnoverScore,
            ),
            strengthScore = entity.strengthScore,
            componentCoverage = entity.componentCoverage,
            rank = entity.rank,
            algorithmVersion = entity.algorithmVersion,
            dataStatus = DataStatus.STALE,
            asOf = entity.asOf,
            isStale = isStale,
        )
    }

    private fun leaderToEntity(taxonomyId: String, leader: TaxonomyLeader, isLeader: Boolean): TaxonomyLeaderEntity {
        return TaxonomyLeaderEntity(
            taxonomyId = taxonomyId,
            securityId = leader.securityId,
            code = leader.code,
            name = leader.name,
            market = leader.market.name,
            returnPct = leader.returnPct,
            latestClose = leader.latestClose,
            foreignNet = leader.foreignNet,
            dataStatus = leader.dataStatus.name,
            isLeader = isLeader,
        )
    }

    private fun entityToLeader(entity: TaxonomyLeaderEntity): TaxonomyLeader {
        return TaxonomyLeader(
            securityId = entity.securityId,
            code = entity.code,
            name = entity.name,
            market = MarketCode.valueOf(entity.market),
            returnPct = entity.returnPct,
            latestClose = entity.latestClose,
            foreignNet = entity.foreignNet,
            dataStatus = DataStatus.STALE,
        )
    }
}
