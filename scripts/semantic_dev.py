"""Development pass: current ten unfamiliar plans through the semantic schema.

These cases were already used to see the old schema fail. They are not held-out.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

CASES = ROOT / "shadowbench" / "semantic-explore" / "cases.json"
OUT = ROOT / "shadowbench" / "semantic-dev" / "live-r2.json"
SUPER = "nvidia/nemotron-3-super-120b-a12b"


def _load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def main() -> None:
    if OUT.exists():
        raise SystemExit("semantic development pass already recorded")
    from pydantic import ValidationError

    from shadow.llm.budget import BudgetError, BudgetLedger
    from shadow.llm.client import LiveDisabled, ResponseCache, SchemaError, model_client, prompt_hash
    from shadow.repair.evaluate import evaluate_repairs
    from shadow.simulation.engine import bind, evaluate_constraints
    from shadow.world.semantic import SemanticWorld, ground_semantic

    _load_env()
    ledger = BudgetLedger(ROOT / "data" / "budget.json")
    baseline = float(ledger.snapshot()["repo_actual_spend_usd"])
    os.environ["SHADOW_SESSION_BASELINE_USD"] = f"{baseline:.8f}"
    os.environ["SHADOW_SESSION_CAP_USD"] = "0.08"
    os.environ["NEBIUS_LIVE"] = "1"
    os.environ["ALLOW_SUPER"] = "true"
    os.environ.pop("ALLOW_ULTRA", None)
    client = model_client(ledger, ResponseCache(ROOT / "data" / "cache.sqlite"))
    rows = []
    for case in json.loads(CASES.read_text()):
        records = [{"id": "user", "text": case["text"]}]
        before = float(ledger.snapshot()["repo_actual_spend_usd"])
        try:
            world = client.complete_json("compile_semantic", {"plan_text": case["plan"], "records": records}, SemanticWorld, model=SUPER)
        except BudgetError:
            raise
        except (SchemaError, ValidationError, LiveDisabled) as exc:
            rows.append({"id": case["id"], "schema_ok": False, "error": str(exc)[:400]})
            continue
        grounded = ground_semantic(world, records, case["plan"])
        failure = None
        if grounded.scenario is not None:
            scored = evaluate_repairs(
                grounded.scenario,
                [(item.id, item.label, item.action_ids, "catalog") for item in grounded.scenario.bundles],
                seed=7,
            )
            keep = next((item for item in scored if item.id == "keep"), None)
            high = {
                var.id: float(var.upper)
                for var in grounded.scenario.variables
                if var.role == "exogenous" and var.upper is not None
            }
            hard = [item.id for item in grounded.scenario.constraints if item.hardness == "hard"]
            high_env = bind(grounded.scenario, {}, high)
            high_values = evaluate_constraints(grounded.scenario, high_env)
            failure = {
                "keep_feasible": None if keep is None else keep.feasible,
                "keep_failures": 0 if keep is None else len(keep.failures),
                "high_violates": any(high_values.get(item) is False for item in hard),
            }
        rows.append(
            {
                "id": case["id"],
                "schema_ok": True,
                "cost_usd": round(max(0.0, float(ledger.snapshot()["repo_actual_spend_usd"]) - before), 8),
                "status": grounded.status,
                "reason": grounded.reason,
                "missing": grounded.missing,
                "contradictions": grounded.contradictions,
                "rejected": grounded.rejected[:6],
                "shown": grounded.shown,
                "failure": failure,
            }
        )
    payload = {
        "model": SUPER,
        "prompt_hash": prompt_hash("compile_semantic.txt"),
        "role": "development, not held-out",
        "cost_usd": round(float(ledger.snapshot()["repo_actual_spend_usd"]) - baseline, 8),
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"cost": payload["cost_usd"], "status": [(row["id"], row.get("status") or row.get("error")) for row in rows]}))


if __name__ == "__main__":
    main()
