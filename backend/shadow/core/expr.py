"""Typed expression IR. Never evaluates raw strings."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UnknownValue:
    """Material value the system refuses to invent."""

    def __repr__(self) -> str:
        return "UNKNOWN"


UNKNOWN = UnknownValue()


class Expr(BaseModel):
    op: str
    ref: str | None = None
    value: Any = None
    args: list[Expr] = Field(default_factory=list)


def evaluate(expr: Expr, env: dict[str, Any]) -> Any:
    op = expr.op
    if op == "var":
        if expr.ref is None or expr.ref not in env:
            return UNKNOWN
        value = env[expr.ref]
        return UNKNOWN if value is None else value
    if op == "const":
        return expr.value
    args = [evaluate(arg, env) for arg in expr.args]
    if any(arg is UNKNOWN for arg in args):
        return UNKNOWN
    if op == "add":
        return sum(args)
    if op == "sub":
        if len(args) == 1:
            return -args[0]
        result = args[0]
        for arg in args[1:]:
            result -= arg
        return result
    if op == "mul":
        result = 1
        for arg in args:
            result *= arg
        return result
    if op == "neg":
        return -args[0]
    if op == "min":
        return min(args)
    if op == "max":
        return max(args)
    if op == "abs":
        return abs(args[0])
    if op == "lte":
        return args[0] <= args[1]
    if op == "gte":
        return args[0] >= args[1]
    if op == "lt":
        return args[0] < args[1]
    if op == "gt":
        return args[0] > args[1]
    if op == "eq":
        return args[0] == args[1]
    if op == "neq":
        return args[0] != args[1]
    if op == "and":
        return all(args)
    if op == "or":
        return any(args)
    if op == "not":
        return not args[0]
    if op == "if":
        return args[1] if args[0] else args[2]
    raise ValueError(f"unsupported expression op: {op}")


def references(expr: Expr) -> set[str]:
    found: set[str] = set()
    if expr.op == "var" and expr.ref:
        found.add(expr.ref)
    for arg in expr.args:
        found |= references(arg)
    return found
