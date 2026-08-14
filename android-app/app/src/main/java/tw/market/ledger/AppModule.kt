package tw.market.ledger

import android.content.Context
import androidx.room.Room
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import tw.market.ledger.database.SecurityDao
import tw.market.ledger.database.ChartDao
import tw.market.ledger.database.TWMarketDatabase
import tw.market.ledger.network.SecurityApi
import tw.market.ledger.network.ChartApi
import tw.market.ledger.network.MarketApi
import tw.market.ledger.database.MarketDao
import tw.market.ledger.database.DerivativesDao
import tw.market.ledger.network.DerivativesApi
import tw.market.ledger.database.PortfolioDao
import tw.market.ledger.network.PortfolioApi
import tw.market.ledger.database.WatchlistDao
import tw.market.ledger.network.WatchlistApi
import tw.market.ledger.database.AlertDao
import tw.market.ledger.network.AlertApi

import tw.market.ledger.database.TaxonomyDao
import tw.market.ledger.network.IndustryApi
import tw.market.ledger.database.MIGRATION_9_10
import tw.market.ledger.database.MIGRATION_10_11
import tw.market.ledger.database.MIGRATION_11_12
import tw.market.ledger.database.CloudSyncDao
import tw.market.ledger.database.ScreenerDao
import tw.market.ledger.network.ScreenerApi
import tw.market.ledger.network.AuthApi
import tw.market.ledger.network.SyncApi
import tw.market.ledger.network.TokenSessionStore
import tw.market.ledger.network.TokenRefresher
import tw.market.ledger.network.BearerAuthInterceptor
import tw.market.ledger.network.RotatingTokenAuthenticator


private val MIGRATION_5_6 = object : Migration(5, 6) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS `watchlist_cache` (`id` TEXT NOT NULL, `name` TEXT NOT NULL, `sortOrder` INTEGER NOT NULL, PRIMARY KEY(`id`))")
        db.execSQL("CREATE TABLE IF NOT EXISTS `watchlist_item_cache` (`watchlistId` TEXT NOT NULL, `id` TEXT NOT NULL, `securityCode` TEXT NOT NULL, `securityName` TEXT NOT NULL, `market` TEXT NOT NULL, `sortOrder` INTEGER NOT NULL, `note` TEXT, `targetPrice` TEXT, `stopPrice` TEXT, `addPrice` TEXT, `close` TEXT, `change` TEXT, `changePercent` TEXT, `priceAsOf` TEXT, `dataStatus` TEXT NOT NULL, `foreignNet` INTEGER, `marginBalanceChange` INTEGER, `priceAboveMa20` INTEGER, PRIMARY KEY(`watchlistId`, `id`))")
    }
}
private val MIGRATION_6_7 = object : Migration(6, 7) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS `alert_rule_cache` (`id` TEXT NOT NULL, `name` TEXT NOT NULL, `ruleType` TEXT NOT NULL, `scopeType` TEXT NOT NULL, `enabled` INTEGER NOT NULL, `maPeriod` INTEGER, `thresholdPrice` TEXT, `thresholdPercent` TEXT, `consecutiveDays` INTEGER, `cooldownMinutes` INTEGER NOT NULL, `dailyLimit` INTEGER NOT NULL, PRIMARY KEY(`id`))")
        db.execSQL("CREATE TABLE IF NOT EXISTS `alert_event_cache` (`id` TEXT NOT NULL, `securityCode` TEXT NOT NULL, `securityName` TEXT NOT NULL, `triggeredAt` TEXT NOT NULL, `tradeDate` TEXT NOT NULL, `eventType` TEXT NOT NULL, `triggerPrice` TEXT NOT NULL, `referenceValue` TEXT NOT NULL, `referenceType` TEXT NOT NULL, `message` TEXT NOT NULL, `dataStatus` TEXT NOT NULL, `readAt` TEXT, PRIMARY KEY(`id`))")
    }
}
private val MIGRATION_7_8 = object : Migration(7, 8) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS `industry_cache` (`id` TEXT NOT NULL, `code` TEXT NOT NULL, `name` TEXT NOT NULL, `classificationSource` TEXT NOT NULL, `memberCount` INTEGER NOT NULL, PRIMARY KEY(`id`))")
        db.execSQL("CREATE TABLE IF NOT EXISTS `theme_cache` (`id` TEXT NOT NULL, `code` TEXT NOT NULL, `name` TEXT NOT NULL, `description` TEXT, `classificationType` TEXT NOT NULL, `memberCount` INTEGER NOT NULL, `createdAt` TEXT, `updatedAt` TEXT, PRIMARY KEY(`id`))")
        db.execSQL("CREATE TABLE IF NOT EXISTS `taxonomy_member_cache` (`taxonomyId` TEXT NOT NULL, `securityId` TEXT NOT NULL, `code` TEXT NOT NULL, `name` TEXT NOT NULL, `market` TEXT NOT NULL, `securityType` TEXT NOT NULL, `isActive` INTEGER NOT NULL, `close` TEXT, `change` TEXT, `changePercent` TEXT, `asOf` TEXT, `dataStatus` TEXT NOT NULL, PRIMARY KEY(`taxonomyId`, `securityId`))")
    }
}
private val MIGRATION_8_9 = object : Migration(8, 9) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS `taxonomy_strength_cache` (`id` TEXT NOT NULL, `taxonomyId` TEXT NOT NULL, `taxonomyCode` TEXT NOT NULL, `taxonomyName` TEXT NOT NULL, `taxonomyType` TEXT NOT NULL, `tradeDate` TEXT NOT NULL, `window` INTEGER NOT NULL, `equalWeightReturn` TEXT NOT NULL, `marketCapWeightedReturn` TEXT, `totalMembers` INTEGER NOT NULL, `validMembers` INTEGER NOT NULL, `coverageRatio` TEXT NOT NULL, `advancers` INTEGER NOT NULL, `decliners` INTEGER NOT NULL, `unchanged` INTEGER NOT NULL, `advanceRatio` TEXT NOT NULL, `aboveMa20Pct` TEXT NOT NULL, `aboveMa60Pct` TEXT NOT NULL, `foreignNetAmount` TEXT NOT NULL, `investmentTrustNetAmount` TEXT NOT NULL, `dealerNetAmount` TEXT NOT NULL, `marginBalanceChange` TEXT NOT NULL, `shortBalanceChange` TEXT NOT NULL, `lendingBalanceChange` TEXT, `turnoverAmount` TEXT, `turnoverShare` TEXT, `turnoverMomentum` TEXT, `momentumScore` TEXT, `breadthScore` TEXT, `technicalScore` TEXT, `institutionalScore` TEXT, `turnoverScore` TEXT, `strengthScore` TEXT, `componentCoverage` TEXT NOT NULL, `rank` INTEGER, `algorithmVersion` TEXT NOT NULL, `dataStatus` TEXT NOT NULL, `asOf` TEXT NOT NULL, PRIMARY KEY(`taxonomyId`, `window`, `tradeDate`))")
        db.execSQL("CREATE TABLE IF NOT EXISTS `taxonomy_leader_cache` (`taxonomyId` TEXT NOT NULL, `securityId` TEXT NOT NULL, `code` TEXT NOT NULL, `name` TEXT NOT NULL, `market` TEXT NOT NULL, `returnPct` TEXT NOT NULL, `latestClose` TEXT, `foreignNet` TEXT, `dataStatus` TEXT NOT NULL, `isLeader` INTEGER NOT NULL, PRIMARY KEY(`taxonomyId`, `securityId`, `isLeader`))")
    }
}


@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides @Singleton
    fun database(@ApplicationContext context: Context): TWMarketDatabase =
        Room.databaseBuilder(context, TWMarketDatabase::class.java, "tw-market-ledger.db")
            .addMigrations(MIGRATION_5_6, MIGRATION_6_7, MIGRATION_7_8, MIGRATION_8_9, MIGRATION_9_10, MIGRATION_10_11, MIGRATION_11_12)
            .build()


    @Provides fun securityDao(database: TWMarketDatabase): SecurityDao = database.securityDao()
    @Provides fun chartDao(database: TWMarketDatabase): ChartDao = database.chartDao()
    @Provides fun marketDao(database: TWMarketDatabase): MarketDao = database.marketDao()
    @Provides fun derivativesDao(database: TWMarketDatabase): DerivativesDao = database.derivativesDao()
    @Provides fun portfolioDao(database: TWMarketDatabase): PortfolioDao = database.portfolioDao()
    @Provides fun watchlistDao(database: TWMarketDatabase): WatchlistDao = database.watchlistDao()
    @Provides fun alertDao(database: TWMarketDatabase): AlertDao = database.alertDao()
    @Provides fun taxonomyDao(database: TWMarketDatabase): TaxonomyDao = database.taxonomyDao()
    @Provides fun screenerDao(database: TWMarketDatabase): ScreenerDao = database.screenerDao()
    @Provides fun cloudSyncDao(database: TWMarketDatabase): CloudSyncDao = database.cloudSyncDao()

    @Provides @Singleton
    fun retrofit(sessionStore: TokenSessionStore, tokenRefresher: TokenRefresher): Retrofit {
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        val client = okhttp3.OkHttpClient.Builder()
            .addInterceptor(BearerAuthInterceptor(sessionStore))
            .authenticator(RotatingTokenAuthenticator(sessionStore, tokenRefresher)).build()
        return Retrofit.Builder().baseUrl(BuildConfig.API_BASE_URL)
            .client(client).addConverterFactory(MoshiConverterFactory.create(moshi)).build()
    }

    @Provides fun tokenStore(store: KeystoreSessionStore): TokenSessionStore = store
    @Provides fun tokenRefresher(manager: AuthSessionManager): TokenRefresher = manager
    @Provides @Singleton fun authApi(retrofit: Retrofit): AuthApi = retrofit.create(AuthApi::class.java)
    @Provides @Singleton fun syncApi(retrofit: Retrofit): SyncApi = retrofit.create(SyncApi::class.java)

    @Provides @Singleton
    fun securityApi(retrofit: Retrofit): SecurityApi = retrofit.create(SecurityApi::class.java)

    @Provides @Singleton
    fun chartApi(retrofit: Retrofit): ChartApi = retrofit.create(ChartApi::class.java)
    @Provides @Singleton fun realtimeApi(retrofit: Retrofit): tw.market.ledger.network.RealtimeApi = retrofit.create(tw.market.ledger.network.RealtimeApi::class.java)

    @Provides @Singleton
    fun marketApi(retrofit: Retrofit): MarketApi = retrofit.create(MarketApi::class.java)

    @Provides @Singleton
    fun derivativesApi(retrofit: Retrofit): DerivativesApi = retrofit.create(DerivativesApi::class.java)

    @Provides @Singleton
    fun portfolioApi(retrofit: Retrofit): PortfolioApi = retrofit.create(PortfolioApi::class.java)
    @Provides @Singleton fun watchlistApi(retrofit: Retrofit): WatchlistApi = retrofit.create(WatchlistApi::class.java)
    @Provides @Singleton fun alertApi(retrofit: Retrofit): AlertApi = retrofit.create(AlertApi::class.java)
    @Provides @Singleton fun industryApi(retrofit: Retrofit): IndustryApi = retrofit.create(IndustryApi::class.java)
    @Provides @Singleton fun screenerApi(retrofit: Retrofit): ScreenerApi = retrofit.create(ScreenerApi::class.java)
    @Provides @Singleton fun comparisonApi(retrofit: Retrofit): tw.market.ledger.network.ComparisonApi = retrofit.create(tw.market.ledger.network.ComparisonApi::class.java)
    @Provides @Singleton fun importExportApi(retrofit: Retrofit): tw.market.ledger.network.ImportExportApi = retrofit.create(tw.market.ledger.network.ImportExportApi::class.java)
    @Provides @Singleton fun aiApi(retrofit: Retrofit): tw.market.ledger.network.AIApi = retrofit.create(tw.market.ledger.network.AIApi::class.java)
    @Provides @Singleton fun pushApi(retrofit: Retrofit): tw.market.ledger.network.PushApi = retrofit.create(tw.market.ledger.network.PushApi::class.java)

    @Provides @Singleton
    fun realtimeQuoteClient(): tw.market.ledger.network.RealtimeQuoteClient =
        tw.market.ledger.network.RealtimeQuoteClient(okhttp3.OkHttpClient())

    @Provides @Singleton
    fun realtimeSubscriptionManager(client: tw.market.ledger.network.RealtimeQuoteClient): tw.market.ledger.network.RealtimeSubscriptionManager =
        tw.market.ledger.network.RealtimeSubscriptionManager(client)

    @Provides
    fun biometricAuthenticator(authenticator: AndroidBiometricAuthenticator): BiometricAuthenticator = authenticator

    @Provides
    fun appPreferences(prefs: AndroidAppPreferences): AppPreferences = prefs
}
