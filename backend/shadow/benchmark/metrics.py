"""Objective ShadowBench metrics. No model is used as a judge."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    systems = sorted({row["system"] for row in rows})
    summary: dict[str, Any] = {"systems": {}, "n": len({row["world_id"] for row in rows})}
    for system in systems:
        subset = [row for row in rows if row["system"] == system]
        summary["systems"][system] = _one(subset)
    return summary


def _one(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    def rate(key: str) -> dict[str, Any]:
        hits = sum(1 for row in rows if row[key])
        return {"count": hits, "n": n, "rate": hits / n if n else 0, "ci95": _bootstrap([1 if row[key] else 0 for row in rows])}

    detected = [row for row in rows if row["oracle_fragile"]]
    undetected = sum(1 for row in detected if row["executed_fails"] and not row["flagged_failure"])
    recall_hits = sum(row["failure_recall_hit"] for row in rows)
    return {
        "TaskCompletionRate": rate("task_complete"),
        "UndetectedFailureRate": {
            "count": undetected,
            "n": len(detected) or n,
            "rate": undetected / len(detected) if detected else 0,
            "ci95": _bootstrap([1 if row["oracle_fragile"] and row["executed_fails"] and not row["flagged_failure"] else 0 for row in rows]),
        },
        "FailureRecall": {
            "count": recall_hits,
            "n": n,
            "rate": recall_hits / n if n else 0,
            "ci95": _bootstrap([row["failure_recall_hit"] for row in rows]),
        },
        "FalseHazardRate": rate("false_hazard"),
        "RepairSuccessRate": rate("repair_success"),
        "RepairRegret": {
            "mean": _mean([row["regret"] for row in rows]),
            "n": n,
        },
        "MinimalCutSetPrecision": _mean([row["cut_precision"] for row in rows if row["cut_precision"] is not None]),
        "MinimalCutSetRecall": _mean([row["cut_recall"] for row in rows if row["cut_recall"] is not None]),
        "UnknownCalibration": rate("unknown_calibrated"),
        "GraphMaterialEdgeRecall": _mean([row["edge_recall"] for row in rows if row.get("edge_recall") is not None]),
        "ExecutionConvergenceRate": rate("converged"),
        "AverageModelCalls": _mean([row["model_calls"] for row in rows]),
        "InputTokens": sum(row["input_tokens"] for row in rows),
        "OutputTokens": sum(row["output_tokens"] for row in rows),
        "CostUSD": sum(row["cost_usd"] for row in rows),
        "LatencyMs": _mean([row["latency_ms"] for row in rows]),
    }


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _bootstrap(values: list[float], draws: int = 400) -> list[float]:
    if not values:
        return [0, 0]
    rng = random.Random(0)
    means = []
    for _ in range(draws):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    low = means[int(0.025 * (len(means) - 1))]
    high = means[int(0.975 * (len(means) - 1))]
    return [round(low, 4), round(high, 4)]


def group_by_system(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["system"]].append(row)
    return grouped
