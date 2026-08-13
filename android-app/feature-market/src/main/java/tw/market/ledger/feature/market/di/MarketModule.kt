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
import tw.market.ledger.network.DerivativesApi
import tw.market.ledger.database.DerivativesDao
import tw.market.ledger.feature.market.data.DefaultDerivativesRepository
import tw.market.ledger.feature.market.domain.DerivativesRepository
import tw.market.ledger.feature.market.domain.GetFuturesOverviewUseCase
import tw.market.ledger.feature.market.data.DefaultRealtimeMarketRepository
import tw.market.ledger.feature.market.domain.RealtimeMarketRepository
import tw.market.ledger.network.RealtimeApi
import tw.market.ledger.network.RealtimeQuoteClient

@Module @InstallIn(SingletonComponent::class)
object MarketModule {
    @Provides fun repository(api: MarketApi, dao: MarketDao): MarketRepository = DefaultMarketRepository(api, dao)
    @Provides fun overview(repository: MarketRepository) = GetMarketOverviewUseCase(repository)
    @Provides fun derivativesRepository(api: DerivativesApi, dao: DerivativesDao): DerivativesRepository =
        DefaultDerivativesRepository(api, dao)
    @Provides fun futuresOverview(repository: DerivativesRepository) = GetFuturesOverviewUseCase(repository)
    @Provides fun realtimeMarketRepository(api: RealtimeApi, client: RealtimeQuoteClient): RealtimeMarketRepository = DefaultRealtimeMarketRepository(api, client)
}
