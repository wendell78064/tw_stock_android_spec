package tw.market.ledger.database
import androidx.room.*
@Entity(tableName="alert_rule_cache",primaryKeys=["id"]) data class AlertRuleEntity(val id:String,val name:String,val ruleType:String,val scopeType:String,val enabled:Boolean,val maPeriod:Int?,val thresholdPrice:String?,val thresholdPercent:String?,val consecutiveDays:Int?,val cooldownMinutes:Int,val dailyLimit:Int)
@Entity(tableName="alert_event_cache",primaryKeys=["id"]) data class AlertEventEntity(val id:String,val securityCode:String,val securityName:String,val triggeredAt:String,val tradeDate:String,val eventType:String,val triggerPrice:String,val referenceValue:String,val referenceType:String,val message:String,val dataStatus:String,val readAt:String?)
@Dao interface AlertDao {
 @Insert(onConflict=OnConflictStrategy.REPLACE) suspend fun upsertRules(rows:List<AlertRuleEntity>); @Insert(onConflict=OnConflictStrategy.REPLACE) suspend fun upsertEvents(rows:List<AlertEventEntity>)
 @Query("DELETE FROM alert_rule_cache") suspend fun clearRules(); @Query("SELECT * FROM alert_rule_cache ORDER BY name") suspend fun rules():List<AlertRuleEntity>
 @Query("SELECT * FROM alert_event_cache ORDER BY triggeredAt DESC") suspend fun events():List<AlertEventEntity>
}
