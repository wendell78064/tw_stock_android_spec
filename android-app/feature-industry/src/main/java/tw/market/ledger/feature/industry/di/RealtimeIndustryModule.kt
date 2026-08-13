package tw.market.ledger.feature.industry.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import tw.market.ledger.feature.industry.data.DefaultRealtimeIndustryRepository
import tw.market.ledger.feature.industry.domain.RealtimeIndustryRepository
import tw.market.ledger.network.RealtimeApi
import tw.market.ledger.network.RealtimeQuoteClient

@Module @InstallIn(SingletonComponent::class)
object RealtimeIndustryModule {
    @Provides fun repository(api: RealtimeApi, client: RealtimeQuoteClient): RealtimeIndustryRepository = DefaultRealtimeIndustryRepository(api, client)
}
