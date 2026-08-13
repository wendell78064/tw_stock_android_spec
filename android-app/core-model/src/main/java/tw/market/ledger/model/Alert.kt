package tw.market.ledger.model
enum class AlertScope { SECURITY, PORTFOLIO, WATCHLIST }
enum class AlertEvaluationMode { EOD, REALTIME }
enum class AlertType { PRICE_TARGET, PRICE_STOP, PRICE_ADD, MA_NEAR, MA_TOUCH, MA_CROSS_ABOVE, MA_CROSS_BELOW, MA_CLOSE_ABOVE, MA_CLOSE_BELOW, MA_CONSECUTIVE_ABOVE, MA_CONSECUTIVE_BELOW }
data class AlertRule(val id:String,val name:String,val type:AlertType,val scope:AlertScope,val enabled:Boolean,val maPeriod:Int?=null,val thresholdPrice:String?=null,val thresholdPercent:String?=null,val consecutiveDays:Int?=null,val cooldownMinutes:Int=1440,val dailyLimit:Int=5,val evaluationMode:AlertEvaluationMode=AlertEvaluationMode.EOD)
data class AlertEvent(val id:String,val securityCode:String,val securityName:String,val triggeredAt:String,val tradeDate:String,val eventType:String,val triggerPrice:String,val referenceValue:String,val referenceType:String,val message:String,val dataStatus:String,val readAt:String?,val evaluationMode:AlertEvaluationMode=AlertEvaluationMode.EOD,val fingerprint:String?=null)
data class AlertDashboard(val rules:List<AlertRule>,val events:List<AlertEvent>,val offline:Boolean=false,val realtimeProviderStatus:String="UNCONFIGURED")
