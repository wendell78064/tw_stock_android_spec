package tw.market.ledger.feature.market.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import tw.market.ledger.database.MarketDao
import tw.market.ledger.feature.market.data.DefaultMarketRepository
import tw.market.ledger.feature.market.domain.GetMarketOverviewUseCase
import tw.market.ledger.feature.market.domain.MarketRepository
import tw.market.ledger.network.MarketApi

@Module @InstallIn(SingletonComponent::class)
object MarketModule {
    @Provides fun repository(api: MarketApi, dao: MarketDao): MarketRepository = DefaultMarketRepository(api, dao)
    @Provides fun overview(repository: MarketRepository) = GetMarketOverviewUseCase(repository)
}
