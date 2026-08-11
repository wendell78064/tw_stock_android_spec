package tw.market.ledger.feature.alert.data
import java.io.IOException
import javax.inject.Inject
import tw.market.ledger.database.*
import tw.market.ledger.feature.alert.domain.AlertRepository
import tw.market.ledger.model.*
import tw.market.ledger.network.*
class DefaultAlertRepository @Inject constructor(private val api:AlertApi,private val dao:AlertDao):AlertRepository {
 override suspend fun dashboard()=try { val rules=api.rules().data; val events=api.notifications().data; dao.clearRules();dao.upsertRules(rules.map(::entity));dao.upsertEvents(events.map(::entity));AlertDashboard(rules.map(::model),events.map(::model)) } catch(_:IOException){ AlertDashboard(dao.rules().map(::model),dao.events().map(::model),true) }
 override suspend fun create(input:AlertRuleInput){api.create(input)};override suspend fun edit(id:String,input:AlertRuleInput){api.edit(id,input)};override suspend fun delete(id:String){api.delete(id)};override suspend fun toggle(id:String,enabled:Boolean){api.toggle(id,if(enabled)"enable" else "disable")};override suspend fun read(id:String){api.read(id)};override suspend fun readAll(){api.readAll()}
}
private fun entity(x:AlertRuleDto)=AlertRuleEntity(x.id,x.name,x.ruleType,x.scopeType,x.enabled,x.maPeriod,x.thresholdPrice,x.thresholdPercent,x.consecutiveDays,x.cooldownMinutes,x.dailyLimit)
private fun entity(x:AlertEventDto)=AlertEventEntity(x.id,x.securityCode,x.securityName,x.triggeredAt,x.tradeDate,x.eventType,x.triggerPrice,x.referenceValue,x.referenceType,x.message,x.dataStatus,x.readAt)
private fun model(x:AlertRuleDto)=AlertRule(x.id,x.name,AlertType.valueOf(x.ruleType),AlertScope.valueOf(x.scopeType),x.enabled,x.maPeriod,x.thresholdPrice,x.thresholdPercent,x.consecutiveDays,x.cooldownMinutes,x.dailyLimit)
private fun model(x:AlertRuleEntity)=AlertRule(x.id,x.name,AlertType.valueOf(x.ruleType),AlertScope.valueOf(x.scopeType),x.enabled,x.maPeriod,x.thresholdPrice,x.thresholdPercent,x.consecutiveDays,x.cooldownMinutes,x.dailyLimit)
private fun model(x:AlertEventDto)=AlertEvent(x.id,x.securityCode,x.securityName,x.triggeredAt,x.tradeDate,x.eventType,x.triggerPrice,x.referenceValue,x.referenceType,x.message,x.dataStatus,x.readAt)
private fun model(x:AlertEventEntity)=AlertEvent(x.id,x.securityCode,x.securityName,x.triggeredAt,x.tradeDate,x.eventType,x.triggerPrice,x.referenceValue,x.referenceType,x.message,x.dataStatus,x.readAt)
