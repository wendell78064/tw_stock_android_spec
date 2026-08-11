package tw.market.ledger.feature.alert.domain
import tw.market.ledger.model.*
interface AlertRepository { suspend fun dashboard():AlertDashboard; suspend fun create(input:tw.market.ledger.network.AlertRuleInput); suspend fun edit(id:String,input:tw.market.ledger.network.AlertRuleInput); suspend fun delete(id:String); suspend fun toggle(id:String,enabled:Boolean); suspend fun read(id:String); suspend fun readAll() }
interface NotificationDeliveryProvider { val status:String }
class LocalNotificationDelivery:NotificationDeliveryProvider { override val status="LOCAL" }
class FutureFcmDelivery:NotificationDeliveryProvider { override val status="UNCONFIGURED" }
