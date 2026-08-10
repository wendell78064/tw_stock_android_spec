package tw.market.ledger

import android.content.Context
import androidx.room.Room
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

@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides @Singleton
    fun database(@ApplicationContext context: Context): TWMarketDatabase =
        Room.databaseBuilder(context, TWMarketDatabase::class.java, "tw-market-ledger.db")
            .fallbackToDestructiveMigration()
            .build()

    @Provides fun securityDao(database: TWMarketDatabase): SecurityDao = database.securityDao()
    @Provides fun chartDao(database: TWMarketDatabase): ChartDao = database.chartDao()
    @Provides fun marketDao(database: TWMarketDatabase): MarketDao = database.marketDao()
    @Provides fun derivativesDao(database: TWMarketDatabase): DerivativesDao = database.derivativesDao()

    @Provides @Singleton
    fun retrofit(): Retrofit {
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        return Retrofit.Builder().baseUrl(BuildConfig.API_BASE_URL)
            .addConverterFactory(MoshiConverterFactory.create(moshi)).build()
    }

    @Provides @Singleton
    fun securityApi(retrofit: Retrofit): SecurityApi = retrofit.create(SecurityApi::class.java)

    @Provides @Singleton
    fun chartApi(retrofit: Retrofit): ChartApi = retrofit.create(ChartApi::class.java)

    @Provides @Singleton
    fun marketApi(retrofit: Retrofit): MarketApi = retrofit.create(MarketApi::class.java)

    @Provides @Singleton
    fun derivativesApi(retrofit: Retrofit): DerivativesApi = retrofit.create(DerivativesApi::class.java)
}
