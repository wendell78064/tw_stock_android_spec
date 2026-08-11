package tw.market.ledger.feature.watchlist.di

import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import tw.market.ledger.feature.watchlist.data.DefaultWatchlistRepository
import tw.market.ledger.feature.watchlist.domain.WatchlistRepository

@Module @InstallIn(SingletonComponent::class)
abstract class WatchlistModule { @Binds abstract fun repository(value: DefaultWatchlistRepository): WatchlistRepository }
