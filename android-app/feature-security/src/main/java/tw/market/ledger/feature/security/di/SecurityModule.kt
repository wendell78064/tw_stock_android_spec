package tw.market.ledger.feature.security.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton
import tw.market.ledger.database.SecurityDao
import tw.market.ledger.feature.security.data.DefaultSecurityRepository
import tw.market.ledger.feature.security.domain.GetSecurityUseCase
import tw.market.ledger.feature.security.domain.SearchSecuritiesUseCase
import tw.market.ledger.feature.security.domain.SecurityRepository
import tw.market.ledger.network.SecurityApi

@Module
@InstallIn(SingletonComponent::class)
object SecurityModule {
    @Provides @Singleton
    fun repository(api: SecurityApi, dao: SecurityDao): SecurityRepository =
        DefaultSecurityRepository(api, dao)

    @Provides fun searchUseCase(repository: SecurityRepository) = SearchSecuritiesUseCase(repository)
    @Provides fun detailUseCase(repository: SecurityRepository) = GetSecurityUseCase(repository)
}

