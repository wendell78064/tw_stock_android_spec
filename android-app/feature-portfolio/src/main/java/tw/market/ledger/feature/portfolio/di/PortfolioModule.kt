package tw.market.ledger.feature.portfolio.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import tw.market.ledger.database.PortfolioDao
import tw.market.ledger.feature.portfolio.data.DefaultPortfolioRepository
import tw.market.ledger.feature.portfolio.domain.PortfolioRepository
import tw.market.ledger.network.PortfolioApi

@Module @InstallIn(SingletonComponent::class)
object PortfolioModule {
    @Provides fun repository(api: PortfolioApi, dao: PortfolioDao): PortfolioRepository =
        DefaultPortfolioRepository(api, dao)
}
