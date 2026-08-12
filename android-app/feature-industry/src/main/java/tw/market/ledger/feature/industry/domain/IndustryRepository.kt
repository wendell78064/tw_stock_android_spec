package tw.market.ledger.feature.industry.domain

import tw.market.ledger.model.Industry
import tw.market.ledger.model.TaxonomyDetail
import tw.market.ledger.model.TaxonomyStrength
import tw.market.ledger.model.TaxonomyStrengthDetail
import tw.market.ledger.model.Theme

interface IndustryRepository {
    suspend fun getIndustries(): Result<Pair<List<Industry>, Boolean>>
    suspend fun getIndustryDetail(id: String): Result<TaxonomyDetail<Industry>>
    suspend fun getThemes(): Result<Pair<List<Theme>, Boolean>>
    suspend fun getThemeDetail(id: String): Result<TaxonomyDetail<Theme>>
    suspend fun getIndustryStrengths(window: Int = 20, sort: String = "strength"): Result<Pair<List<TaxonomyStrength>, Boolean>>
    suspend fun getThemeStrengths(window: Int = 20, sort: String = "strength"): Result<Pair<List<TaxonomyStrength>, Boolean>>
    suspend fun getTaxonomyStrengthDetail(id: String, isIndustry: Boolean, window: Int = 20): Result<TaxonomyStrengthDetail>
    suspend fun getTaxonomyStrengthHistory(id: String, isIndustry: Boolean, window: Int = 20, limit: Int = 60): Result<Pair<List<TaxonomyStrength>, Boolean>>
}
