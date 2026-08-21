package tw.market.ledger.feature.security.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.hilt.android.qualifiers.ApplicationContext
import android.content.Context
import javax.inject.Singleton
import tw.market.ledger.database.SecurityDao
import tw.market.ledger.database.ChartDao
import tw.market.ledger.feature.security.data.DefaultSecurityRepository
import tw.market.ledger.feature.security.data.DefaultChartRepository
import tw.market.ledger.feature.security.data.IndicatorSettings
import tw.market.ledger.feature.security.domain.ChartRepository
import tw.market.ledger.feature.security.domain.GetSecurityChartUseCase
import tw.market.ledger.feature.security.domain.GetSecurityUseCase
import tw.market.ledger.feature.security.domain.SearchSecuritiesUseCase
import tw.market.ledger.feature.security.domain.SecurityRepository
import tw.market.ledger.network.SecurityApi
import tw.market.ledger.network.ChartApi
import tw.market.ledger.network.RealtimeApi
import tw.market.ledger.network.RealtimeQuoteClient
import tw.market.ledger.network.RealtimeSubscriptionManager
import tw.market.ledger.feature.security.data.DefaultIntradayRepository
import tw.market.ledger.feature.security.domain.IntradayRepository

@Module
@InstallIn(SingletonComponent::class)
object SecurityModule {
    @Provides @Singleton
    fun repository(api: SecurityApi, dao: SecurityDao): SecurityRepository =
        DefaultSecurityRepository(api, dao)

    @Provides fun searchUseCase(repository: SecurityRepository) = SearchSecuritiesUseCase(repository)
    @Provides fun detailUseCase(repository: SecurityRepository) = GetSecurityUseCase(repository)
    @Provides fun analysisPromptUseCase(repository: SecurityRepository) = tw.market.ledger.feature.security.domain.GetAnalysisPromptUseCase(repository)

    @Provides @Singleton
    fun chartRepository(api: ChartApi, dao: ChartDao): ChartRepository = DefaultChartRepository(api, dao)

    @Provides fun chartUseCase(repository: ChartRepository) = GetSecurityChartUseCase(repository)

    @Provides @Singleton
    fun indicatorSettings(@ApplicationContext context: Context) = IndicatorSettings(context)

    @Provides @Singleton fun intradayRepository(
        api: RealtimeApi, client: RealtimeQuoteClient, subscriptions: RealtimeSubscriptionManager,
    ): IntradayRepository = DefaultIntradayRepository(api, client, subscriptions)
}
