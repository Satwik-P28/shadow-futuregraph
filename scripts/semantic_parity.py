"""Compare explicit Nemotron models through the product semantic pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

MODELS = (
    "nvidia/Nemotron-3_5-Lightning",
    "nvidia/nemotron-3-super-120b-a12b",
)
CASES = ROOT / "shadowbench" / "semantic-explore" / "cases.json"
ORACLE = ROOT / "shadowbench" / "semantic-explore" / "oracle.json"


def _case(client: Any, model: str, case: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    from shadow.repair.evaluate import evaluate_repairs
    from shadow.simulation.engine import bind, evaluate_constraints
    from shadow.world.semantic import SemanticWorld, ground_semantic

    records = [{"id": "user", "text": case["text"]}]
    context = {"plan_text": case["plan"], "records": records}
    started = time.perf_counter()
    try:
        world = client.complete_json("compile_semantic", context, SemanticWorld, model=model)
        grounded = ground_semantic(world, records, case["plan"])
    except Exception as exc:
        return {
            "id": case["id"],
            "model": model,
            "status": "ERROR",
            "error": type(exc).__name__,
            "latency_s": round(time.perf_counter() - started, 3),
        }
    scenario = grounded.scenario
    decision = None
    repairs = 0
    if scenario is not None:
        values = evaluate_constraints(scenario, bind(scenario, {}, {}))
        hard = [item.id for item in scenario.constraints if item.hardness == "hard"]
        decision = all(values.get(item) is True for item in hard)
        scored = evaluate_repairs(
            scenario,
            [(item.id, item.label, item.action_ids, "catalog") for item in scenario.bundles],
            seed=7,
        )
        repairs = sum(item.feasible for item in scored)
    call = client.calls[-1] if client.calls else {}
    rejected_links = sum(item.startswith("link ") for item in grounded.rejected)
    return {
        "id": case["id"],
        "model": model,
        "schema_valid": call.get("schema_valid"),
        "facts": len(world.facts),
        "links": len(world.links),
        "links_rejected": rejected_links,
        "facts_rejected": len(grounded.rejected) - rejected_links,
        "obligations_missed": sum(item.status == "UNRESOLVED" for item in grounded.obligations),
        "status": grounded.status,
        "expected": expected.get("expected"),
        "status_correct": grounded.status == expected.get("expected"),
        "decision": decision,
        "repair_count": repairs,
        "latency_s": round(time.perf_counter() - started, 3),
        "cost_usd": call.get("actual_cost_usd", 0),
        "rejected": grounded.rejected,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--models", nargs="*", default=list(MODELS), choices=list(MODELS))
    args = parser.parse_args()

    from shadow.llm.budget import BudgetLedger
    from shadow.llm.client import ResponseCache, model_client

    os.environ.setdefault("SHADOW_SESSION_CAP_USD", "0.03")
    os.environ.setdefault("SHADOW_SESSION_BASELINE_USD", "0")
    cases = json.loads(CASES.read_text())[: args.limit]
    oracle = json.loads(ORACLE.read_text())
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        ledger = BudgetLedger(root / "budget.json")
        client = model_client(ledger, ResponseCache(root / "cache.sqlite"))
        rows = [_case(client, model, case, oracle[case["id"]]) for model in args.models for case in cases]
        print(json.dumps({"rows": rows, "spend_usd": ledger.snapshot()["repo_actual_spend_usd"]}, indent=2))


if __name__ == "__main__":
    main()
