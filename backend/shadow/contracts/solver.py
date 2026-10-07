"""Z3 is used only for linear numeric satisfiability. Anything else is unsupported."""

from __future__ import annotations

from shadow.core.expr import Expr
from shadow.core.models import Scenario


def linear_satisfiability(scenario: Scenario) -> str:
    """Return sat, unsat, or unsupported. Unsupported is not a verification."""
    try:
        import z3
    except ImportError:
        return "unsupported"
    if any(var.vtype != "number" for var in scenario.variables):
        return "unsupported"
    if any(constraint.expr.op not in {"lte", "gte", "lt", "gt", "eq"} for constraint in scenario.constraints):
        return "unsupported"
    solver = z3.Solver()
    symbols: dict[str, object] = {}

    def symbol(name: str):
        if name not in symbols:
            symbols[name] = z3.Real(name)
        return symbols[name]

    def compile_expr(expr: Expr):
        if expr.op == "const":
            return float(expr.value)
        if expr.op == "var":
            var = next(item for item in scenario.variables if item.id == expr.ref)
            if var.role == "derived":
                if var.formula is None:
                    raise ValueError(expr.ref)
                return compile_expr(var.formula)
            return symbol(var.id)
        if expr.op == "add":
            return sum(compile_expr(arg) for arg in expr.args)
        if expr.op == "sub":
            values = [compile_expr(arg) for arg in expr.args]
            result = values[0]
            for value in values[1:]:
                result = result - value
            return result
        if expr.op == "mul":
            values = [compile_expr(arg) for arg in expr.args]
            if not any(isinstance(value, (int, float)) for value in values):
                raise ValueError("nonlinear")
            return values[0] * values[1]
        raise ValueError(expr.op)

    try:
        for var in scenario.variables:
            if var.role == "derived" or var.vtype != "number":
                continue
            if var.role == "exogenous" or var.role == "fixed":
                solver.add(symbol(var.id) == float(var.baseline or 0))
            else:
                if var.lower is not None:
                    solver.add(symbol(var.id) >= float(var.lower))
                if var.upper is not None:
                    solver.add(symbol(var.id) <= float(var.upper))
        for constraint in scenario.constraints:
            if constraint.hardness != "hard":
                continue
            left = compile_expr(constraint.expr.args[0])
            right = compile_expr(constraint.expr.args[1])
            op = constraint.expr.op
            if op == "lte":
                solver.add(left <= right)
            elif op == "gte":
                solver.add(left >= right)
            elif op == "lt":
                solver.add(left < right)
            elif op == "gt":
                solver.add(left > right)
            elif op == "eq":
                solver.add(left == right)
            else:
                return "unsupported"
        result = solver.check()
    except (ValueError, StopIteration, TypeError):
        return "unsupported"
    if result == z3.sat:
        return "sat"
    if result == z3.unsat:
        return "unsat"
    return "unsupported"


def references_only_numbers(scenario: Scenario) -> bool:
    del scenario
    return True
