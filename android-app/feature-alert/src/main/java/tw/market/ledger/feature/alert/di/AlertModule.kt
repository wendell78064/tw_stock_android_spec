package tw.market.ledger.feature.alert.di
import dagger.*;import dagger.hilt.InstallIn;import dagger.hilt.components.SingletonComponent;import tw.market.ledger.feature.alert.data.DefaultAlertRepository;import tw.market.ledger.feature.alert.domain.AlertRepository
@Module @InstallIn(SingletonComponent::class) abstract class AlertModule {@Binds abstract fun repository(value:DefaultAlertRepository):AlertRepository}
