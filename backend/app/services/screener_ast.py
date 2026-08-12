from typing import Any

from app.core.exceptions import AppError
from app.domain.screener import (
    SCREENER_FIELDS_REGISTRY,
    FieldType,
    ScreenerExpression,
    ScreenerOperator,
)


def validate_expression(expr: ScreenerExpression) -> None:
    if expr.type not in ("CONDITION", "AND", "OR"):
        raise AppError("INVALID_AST_NODE_TYPE", f"Unknown AST node type: {expr.type}")

    if expr.type == "CONDITION":
        if not expr.field or expr.field not in SCREENER_FIELDS_REGISTRY:
            raise AppError("INVALID_AST_FIELD", f"Field '{expr.field}' is not in whitelist registry")

        meta = SCREENER_FIELDS_REGISTRY[expr.field]

        if not expr.operator or expr.operator not in meta.allowed_operators:
            raise AppError(
                "INVALID_AST_OPERATOR",
                f"Operator '{expr.operator}' is not allowed for field '{expr.field}'",
            )

        op = expr.operator
        if op in (ScreenerOperator.IS_AVAILABLE, ScreenerOperator.IS_UNAVAILABLE):
            return

        if op == ScreenerOperator.BETWEEN:
            if expr.value is None or expr.value2 is None:
                raise AppError("INVALID_AST_VALUE", f"Operator BETWEEN requires value and value2 for field '{expr.field}'")
        elif op in (ScreenerOperator.IN, ScreenerOperator.NOT_IN):
            if not isinstance(expr.value, list | tuple):
                raise AppError("INVALID_AST_VALUE", f"Operator {op} requires list value for field '{expr.field}'")
        else:
            if expr.value is None:
                raise AppError("INVALID_AST_VALUE", f"Operator {op} requires non-null value for field '{expr.field}'")

    else:  # AND / OR
        if not expr.children:
            raise AppError("INVALID_AST_GROUP", f"Logical group '{expr.type}' must have at least one child")
        for child in expr.children:
            validate_expression(child)


def dict_to_expression(data: dict[str, Any]) -> ScreenerExpression:
    if not isinstance(data, dict):
        raise AppError("INVALID_AST_FORMAT", "AST node must be a dict")

    node_type = data.get("type")
    if not node_type:
        raise AppError("INVALID_AST_FORMAT", "AST node missing 'type'")

    if node_type == "CONDITION":
        op_raw = data.get("operator")
        op_enum = ScreenerOperator(op_raw) if op_raw else None
        return ScreenerExpression(
            type="CONDITION",
            field=data.get("field"),
            operator=op_enum,
            value=data.get("value"),
            value2=data.get("value2"),
        )
    elif node_type in ("AND", "OR"):
        children_raw = data.get("children", [])
        if not isinstance(children_raw, list):
            raise AppError("INVALID_AST_FORMAT", "Group 'children' must be a list")
        children = [dict_to_expression(c) for c in children_raw]
        return ScreenerExpression(type=node_type, children=children)
    else:
        raise AppError("INVALID_AST_NODE_TYPE", f"Unknown AST node type: {node_type}")


def expression_to_dict(expr: ScreenerExpression) -> dict[str, Any]:
    if expr.type == "CONDITION":
        res = {
            "type": "CONDITION",
            "field": expr.field,
            "operator": expr.operator.value if expr.operator else None,
            "value": expr.value,
        }
        if expr.value2 is not None:
            res["value2"] = expr.value2
        return res
    else:
        return {
            "type": expr.type,
            "children": [expression_to_dict(c) for c in expr.children],
        }
