package tw.market.ledger.network
import com.squareup.moshi.Json
import retrofit2.http.*
data class AlertRuleDto(val id:String,val name:String,@Json(name="rule_type") val ruleType:String,@Json(name="scope_type") val scopeType:String,val enabled:Boolean,@Json(name="ma_period") val maPeriod:Int?=null,@Json(name="threshold_price") val thresholdPrice:String?=null,@Json(name="threshold_percent") val thresholdPercent:String?=null,@Json(name="consecutive_days") val consecutiveDays:Int?=null,@Json(name="cooldown_minutes") val cooldownMinutes:Int=1440,@Json(name="daily_limit") val dailyLimit:Int=5)
data class AlertRuleInput(val name:String,@Json(name="rule_type") val ruleType:String,@Json(name="scope_type") val scopeType:String,@Json(name="security_id") val securityId:String?=null,@Json(name="portfolio_id") val portfolioId:String?=null,@Json(name="watchlist_id") val watchlistId:String?=null,@Json(name="ma_period") val maPeriod:Int?=null,@Json(name="threshold_price") val thresholdPrice:String?=null,@Json(name="threshold_percent") val thresholdPercent:String?=null,@Json(name="consecutive_days") val consecutiveDays:Int?=null,val enabled:Boolean=true,@Json(name="cooldown_minutes") val cooldownMinutes:Int=1440,@Json(name="daily_limit") val dailyLimit:Int=5)
data class AlertEventDto(val id:String,@Json(name="security_code") val securityCode:String,@Json(name="security_name") val securityName:String,@Json(name="triggered_at") val triggeredAt:String,@Json(name="trade_date") val tradeDate:String,@Json(name="event_type") val eventType:String,@Json(name="trigger_price") val triggerPrice:String,@Json(name="reference_value") val referenceValue:String,@Json(name="reference_type") val referenceType:String,val message:String,@Json(name="data_status") val dataStatus:String,@Json(name="read_at") val readAt:String?)
data class AlertRulesEnvelope(val data:List<AlertRuleDto>); data class AlertRuleEnvelope(val data:AlertRuleDto); data class AlertEventsEnvelope(val data:List<AlertEventDto>)
interface AlertApi {
 @GET("alerts/rules") suspend fun rules():AlertRulesEnvelope
 @POST("alerts/rules") suspend fun create(@Body input:AlertRuleInput):AlertRuleEnvelope
 @PATCH("alerts/rules/{id}") suspend fun edit(@Path("id") id:String,@Body input:AlertRuleInput):AlertRuleEnvelope
 @DELETE("alerts/rules/{id}") suspend fun delete(@Path("id") id:String)
 @POST("alerts/rules/{id}/{action}") suspend fun toggle(@Path("id") id:String,@Path("action") action:String):AlertRuleEnvelope
 @GET("notifications") suspend fun notifications(@Query("unread_only") unread:Boolean=false):AlertEventsEnvelope
 @POST("notifications/{id}/read") suspend fun read(@Path("id") id:String)
 @POST("notifications/read-all") suspend fun readAll()
}
