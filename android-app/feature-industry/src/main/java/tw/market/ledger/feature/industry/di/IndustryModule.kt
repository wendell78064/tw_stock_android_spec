package tw.market.ledger.feature.industry.di

import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import tw.market.ledger.feature.industry.data.IndustryRepositoryImpl
import tw.market.ledger.feature.industry.domain.IndustryRepository
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class IndustryModule {
    @Binds
    @Singleton
    abstract fun bindIndustryRepository(
        impl: IndustryRepositoryImpl,
    ): IndustryRepository
}
