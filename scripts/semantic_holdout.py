"""One frozen pass of the semantic compiler on cases that were not used for tuning.

The case file is hashed before the first model call. A second run is refused.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

CASES = ROOT / "shadowbench" / "semantic-holdout" / "cases.json"
OUT = ROOT / "shadowbench" / "semantic-holdout" / "live.json"
FROZEN = ROOT / "shadowbench" / "semantic-holdout" / "FROZEN.sha256"
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


def _hit(case: dict, row: dict) -> bool:
    status = row.get("status")
    failure = row.get("failure") or {}
    if case["expect"] != status:
        return False
    check = case["check"]
    if check == "high_miss":
        return bool(failure.get("high_violates"))
    if check == "over_budget":
        return failure.get("keep_feasible") is False or bool(failure.get("high_violates"))
    if check == "conflict_nominal":
        return failure.get("keep_feasible") is False or bool(failure.get("high_violates"))
    if check == "none":
        return failure.get("keep_feasible") is True and not failure.get("high_violates")
    return True


def main() -> None:
    if OUT.exists():
        raise SystemExit("semantic holdout already recorded")
    digest = hashlib.sha256(CASES.read_bytes()).hexdigest()
    FROZEN.write_text(digest + "\n")
    from pydantic import ValidationError

    from shadow.llm.budget import BudgetError, BudgetLedger
    from shadow.llm.client import LiveDisabled, ResponseCache, SchemaError, model_client, prompt_hash
    from shadow.repair.evaluate import evaluate_repairs
    from shadow.simulation.engine import bind, evaluate_constraints
    from shadow.world.executable import compile_primitives
    from shadow.world.semantic import SemanticWorld, ground_semantic

    cases = json.loads(CASES.read_text())
    grammar = []
    for case in cases:
        compiled = compile_primitives(case["plan"], [{"id": "user", "text": case["text"]}])
        grammar.append({"id": case["id"], "status": compiled.status})

    _load_env()
    ledger = BudgetLedger(ROOT / "data" / "budget.json")
    baseline = float(ledger.snapshot()["repo_actual_spend_usd"])
    os.environ["SHADOW_SESSION_BASELINE_USD"] = f"{baseline:.8f}"
    os.environ["SHADOW_SESSION_CAP_USD"] = "0.12"
    os.environ["NEBIUS_LIVE"] = "1"
    os.environ["ALLOW_SUPER"] = "true"
    os.environ.pop("ALLOW_ULTRA", None)
    client = model_client(ledger, ResponseCache(ROOT / "data" / "cache.sqlite"))
    rows = []
    for case in cases:
        records = [{"id": "user", "text": case["text"]}]
        before = float(ledger.snapshot()["repo_actual_spend_usd"])
        try:
            world = client.complete_json(
                "compile_semantic",
                {"plan_text": case["plan"], "records": records},
                SemanticWorld,
                model=SUPER,
            )
        except BudgetError:
            raise
        except (SchemaError, ValidationError, LiveDisabled) as exc:
            rows.append({"id": case["id"], "schema_ok": False, "error": str(exc)[:400], "hit": False})
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
        row = {
            "id": case["id"],
            "schema_ok": True,
            "cost_usd": round(max(0.0, float(ledger.snapshot()["repo_actual_spend_usd"]) - before), 8),
            "expect": case["expect"],
            "check": case["check"],
            "status": grounded.status,
            "reason": grounded.reason,
            "missing": grounded.missing,
            "contradictions": grounded.contradictions,
            "rejected": grounded.rejected[:6],
            "shown": grounded.shown,
            "failure": failure,
        }
        row["hit"] = _hit(case, row)
        rows.append(row)
    hits = sum(1 for row in rows if row.get("hit"))
    payload = {
        "model": SUPER,
        "prompt_hash": prompt_hash("compile_semantic.txt"),
        "dataset_sha256": digest,
        "role": "frozen holdout, scored once",
        "independence": "Written by the compiler author after the development ten. Not a separate human author. Not the grammar templates.",
        "grammar_status": grammar,
        "grammar_executable": sum(1 for item in grammar if item["status"] == "EXECUTABLE"),
        "cost_usd": round(float(ledger.snapshot()["repo_actual_spend_usd"]) - baseline, 8),
        "hits": hits,
        "n": len(rows),
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"cost": payload["cost_usd"], "hits": hits, "n": len(rows), "grammar_executable": payload["grammar_executable"]}))


if __name__ == "__main__":
    main()
