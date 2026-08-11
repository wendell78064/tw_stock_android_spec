from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from app.core.dependencies import alert_repository
from app.domain.alert import (
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_DAILY_LIMIT,
    AlertRuleType,
    AlertScopeType,
)
from app.services.alerts import AlertEvaluationService, AlertRuleService

router = APIRouter(tags=["Alerts"])


class RuleInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    rule_type: AlertRuleType
    scope_type: AlertScopeType
    security_id: UUID | None = None
    portfolio_id: UUID | None = None
    watchlist_id: UUID | None = None
    ma_period: int | None = None
    threshold_price: Decimal | None = None
    threshold_percent: Decimal | None = None
    consecutive_days: int | None = None
    enabled: bool = True
    cooldown_minutes: int = Field(default=DEFAULT_COOLDOWN_MINUTES, ge=0)
    daily_limit: int = Field(default=DEFAULT_DAILY_LIMIT, ge=1)


Repo = Annotated[object, Depends(alert_repository)]


def rule(r):
    return {
        "id": str(r.id),
        "name": r.name,
        "rule_type": r.rule_type.value,
        "scope_type": r.scope_type.value,
        "security_id": str(r.security_id) if r.security_id else None,
        "portfolio_id": str(r.portfolio_id) if r.portfolio_id else None,
        "watchlist_id": str(r.watchlist_id) if r.watchlist_id else None,
        "ma_period": r.ma_period,
        "threshold_price": str(r.threshold_price) if r.threshold_price is not None else None,
        "threshold_percent": str(r.threshold_percent) if r.threshold_percent is not None else None,
        "consecutive_days": r.consecutive_days,
        "enabled": r.enabled,
        "cooldown_minutes": r.cooldown_minutes,
        "daily_limit": r.daily_limit,
    }


def event(e):
    return {
        "id": str(e.id),
        "alert_rule_id": str(e.alert_rule_id),
        "security_id": str(e.security_id),
        "security_code": e.security_code,
        "security_name": e.security_name,
        "triggered_at": e.triggered_at.isoformat(),
        "trade_date": e.trade_date.isoformat(),
        "event_type": e.event_type,
        "trigger_price": str(e.trigger_price),
        "reference_value": str(e.reference_value),
        "reference_type": e.reference_type,
        "message": e.message,
        "data_status": e.data_status.value,
        "notification_eligible": e.notification_eligible,
        "read_at": e.read_at.isoformat() if e.read_at else None,
    }


def values(p):
    return p.model_dump()


@router.get("/alerts/rules", operation_id="listAlertRules")
async def list_rules(repository: Repo):
    return {"data": [rule(x) for x in await repository.list_rules()]}


@router.post("/alerts/rules", status_code=201, operation_id="createAlertRule")
async def create_rule(payload: RuleInput, repository: Repo):
    return {"data": rule(await AlertRuleService(repository).save(values(payload)))}


@router.get("/alerts/rules/{rule_id}", operation_id="getAlertRule")
async def get_rule(rule_id: UUID, repository: Repo):
    return {"data": rule(await AlertRuleService(repository).require(rule_id))}


@router.patch("/alerts/rules/{rule_id}", operation_id="updateAlertRule")
async def update_rule(rule_id: UUID, payload: RuleInput, repository: Repo):
    return {"data": rule(await AlertRuleService(repository).save(values(payload), rule_id))}


@router.delete("/alerts/rules/{rule_id}", status_code=204, operation_id="deleteAlertRule")
async def delete_rule(rule_id: UUID, repository: Repo):
    await AlertRuleService(repository).require(rule_id)
    await repository.delete_rule(rule_id)
    return Response(status_code=204)


@router.post("/alerts/rules/{rule_id}/{action}", operation_id="toggleAlertRule")
async def toggle(rule_id: UUID, action: str, repository: Repo):
    await AlertRuleService(repository).require(rule_id)
    if action not in {"enable", "disable"}:
        return Response(status_code=404)
    await repository.set_enabled(rule_id, action == "enable")
    return {"data": rule(await repository.get_rule(rule_id))}


@router.post("/alerts/evaluate", operation_id="evaluateAlerts")
async def evaluate_alerts(repository: Repo, target_trade_date: date | None = None):
    return {"data": await AlertEvaluationService(repository).evaluate(target_trade_date)}


@router.get("/alerts/events", operation_id="listAlertEvents")
async def alert_events(repository: Repo, limit: int = Query(50, ge=1, le=200)):
    return {"data": [event(x) for x in await repository.list_events(limit=limit)]}


@router.get("/notifications", operation_id="listNotifications")
async def notifications(
    repository: Repo,
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    event_type: str | None = None,
    security: str | None = None,
):
    return {
        "data": [
            event(x) for x in await repository.list_events(unread_only, limit, event_type, security)
        ]
    }


@router.post("/notifications/read-all", operation_id="readAllNotifications")
async def read_all(repository: Repo):
    await repository.mark_all_read()
    return {"data": {"read_all": True}}


@router.post("/notifications/{event_id}/read", operation_id="readNotification")
async def read_notification(event_id: UUID, repository: Repo):
    if not await repository.mark_read(event_id):
        return Response(status_code=404)
    return {"data": {"id": str(event_id), "read": True}}
