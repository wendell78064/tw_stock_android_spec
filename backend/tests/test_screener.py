from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from starlette.testclient import TestClient

from app.core.exceptions import AppError
from app.domain.market import DataStatus, MarketCode
from app.domain.screener import (
    SavedScreener,
    ScreenerExpression,
    ScreenerOperator,
    ScreenerResultSecurity,
)
from app.services.screener_ast import (
    dict_to_expression,
    expression_to_dict,
    validate_expression,
)


class InMemoryScreenerRepository:

    def __init__(self):
        self.screeners: dict[UUID, SavedScreener] = {}

    async def list_screeners(self):
        return list(self.screeners.values())

    async def get_screener(self, id):
        return self.screeners.get(id)

    async def create_screener(
        self,
        name,
        expression,
        description=None,
        sort_field="code",
        sort_direction="ASC",
    ):
        sid = uuid4()
        now = datetime.now(UTC)
        screener = SavedScreener(
            id=sid,
            name=name,
            description=description,
            expression=expression,
            sort_field=sort_field,
            sort_direction=sort_direction,
            created_at=now,
            updated_at=now,
        )
        self.screeners[sid] = screener
        return screener

    async def update_screener(
        self,
        id,
        name=None,
        description=None,
        expression=None,
        sort_field=None,
        sort_direction=None,
    ):
        s = self.screeners.get(id)
        if not s:
            return None
        updated = SavedScreener(
            id=s.id,
            name=name if name is not None else s.name,
            description=description if description is not None else s.description,
            expression=expression if expression is not None else s.expression,
            sort_field=sort_field if sort_field is not None else s.sort_field,
            sort_direction=sort_direction if sort_direction is not None else s.sort_direction,
            created_at=s.created_at,
            updated_at=datetime.now(UTC),
        )
        self.screeners[id] = updated
        return updated

    async def delete_screener(self, id):
        if id in self.screeners:
            del self.screeners[id]
            return True
        return False


class InMemoryScreenerQueryService:

    async def execute_screener(
        self,
        expression,
        target_trade_date=None,
        sort_field="code",
        sort_direction="ASC",
        limit=50,
        offset=0,
    ):
        trade_date = target_trade_date or date(2026, 8, 11)
        res = ScreenerResultSecurity(
            security_id=uuid4(),
            code="2330",
            name="台積電",
            market=MarketCode.TWSE,
            industry_name="半導體業",
            themes=["AI概念股", "先進製程"],
            close="950.00",
            return_pct="2.50",
            matched_conditions=["close GT 900.00", "rsi14 LT 70.00"],
            extra_metrics={"rsi14": "62.50", "foreign_5d_net": "5000000"},
            data_status=DataStatus.FINAL,
        )
        return [res], 1, trade_date


def test_ast_validation_valid():
    expr = ScreenerExpression(
        type="AND",
        children=[
            ScreenerExpression(type="CONDITION", field="close", operator=ScreenerOperator.GT, value=500),
            ScreenerExpression(type="CONDITION", field="rsi14", operator=ScreenerOperator.BETWEEN, value=30, value2=70),
        ],
    )
    validate_expression(expr)  # should not raise


def test_ast_validation_invalid_field():
    expr = ScreenerExpression(type="CONDITION", field="non_existent_field", operator=ScreenerOperator.GT, value=100)
    with pytest.raises(AppError) as exc:
        validate_expression(expr)
    assert exc.value.code == "INVALID_AST_FIELD"


def test_ast_validation_invalid_operator():
    expr = ScreenerExpression(type="CONDITION", field="close", operator=ScreenerOperator.IN, value="string")
    with pytest.raises(AppError) as exc:
        validate_expression(expr)
    assert exc.value.code == "INVALID_AST_VALUE"


def test_ast_dict_conversion():
    data = {
        "type": "AND",
        "children": [
            {"type": "CONDITION", "field": "close", "operator": "GT", "value": 100},
            {"type": "CONDITION", "field": "industry_name", "operator": "EQ", "value": "半導體業"},
        ],
    }
    expr = dict_to_expression(data)
    assert expr.type == "AND"
    assert len(expr.children) == 2
    assert expr.children[0].field == "close"
    assert expr.children[0].operator == ScreenerOperator.GT

    serialized = expression_to_dict(expr)
    assert serialized == data


def test_api_get_screener_fields(client: TestClient):
    response = client.get("/v1/screener/fields")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 10
    field_ids = [f["field_id"] for f in data]
    assert "close" in field_ids
    assert "rsi14" in field_ids
    assert "industry_strength_score" in field_ids


def test_api_run_screener(client: TestClient, app_client):
    app, client = app_client
    app.dependency_overrides[
        "app.core.dependencies.screener_query_service"
    ] = lambda: InMemoryScreenerQueryService()

    payload = {
        "expression": {
            "type": "AND",
            "children": [
                {"type": "CONDITION", "field": "close", "operator": "GT", "value": 500},
            ],
        },
        "sort_field": "code",
        "sort_direction": "ASC",
        "limit": 10,
    }
    response = client.post("/v1/screener/run", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["total_count"] == 1
    assert res["data"][0]["code"] == "2330"


def test_api_saved_screener_crud(client: TestClient, app_client):
    app, client = app_client
    in_memory_repo = InMemoryScreenerRepository()
    app.dependency_overrides[
        "app.core.dependencies.screener_repository"
    ] = lambda: in_memory_repo

    # Create
    create_payload = {
        "name": "強勢半導體",
        "description": "篩選高股價且強勢半導體",
        "expression": {
            "type": "CONDITION",
            "field": "close",
            "operator": "GT",
            "value": 800,
        },
    }
    create_res = client.post("/v1/screeners", json=create_payload)
    assert create_res.status_code == 201
    sid = create_res.json()["data"]["id"]

    # List
    list_res = client.get("/v1/screeners")
    assert list_res.status_code == 200
    assert len(list_res.json()["data"]) == 1

    # Get
    get_res = client.get(f"/v1/screeners/{sid}")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["name"] == "強勢半導體"

    # Patch
    patch_res = client.patch(f"/v1/screeners/{sid}", json={"name": "熱門標的"})
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["name"] == "熱門標的"

    # Delete
    del_res = client.delete(f"/v1/screeners/{sid}")
    assert del_res.status_code == 204

    # Verify deleted
    get_after_del = client.get(f"/v1/screeners/{sid}")
    assert get_after_del.status_code == 404
