package tw.market.ledger.feature.industry.domain

import tw.market.ledger.model.Industry
import tw.market.ledger.model.TaxonomyDetail
import tw.market.ledger.model.Theme

interface IndustryRepository {
    suspend fun getIndustries(): Result<Pair<List<Industry>, Boolean>>
    suspend fun getIndustryDetail(id: String): Result<TaxonomyDetail<Industry>>
    suspend fun getThemes(): Result<Pair<List<Theme>, Boolean>>
    suspend fun getThemeDetail(id: String): Result<TaxonomyDetail<Theme>>
}
