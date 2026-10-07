"""One live pass of the current executable schema on ten unfamiliar plans.

Does not edit the prompt or the cases. Refuses a second live pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

OUT = ROOT / "shadowbench" / "semantic-explore"
CASES = OUT / "cases.json"
ORACLE = OUT / "oracle.json"
FROZEN = OUT / "FROZEN.sha256"
SUPER = "nvidia/nemotron-3-super-120b-a12b"


def _freeze() -> str:
    digest = hashlib.sha256(CASES.read_bytes() + ORACLE.read_bytes()).hexdigest()
    if FROZEN.exists() and FROZEN.read_text().strip() != digest:
        raise SystemExit("semantic explore set changed after it was frozen")
    if not FROZEN.exists():
        FROZEN.write_text(digest + "\n")
    return digest


def _load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _grammar(cases: list[dict]) -> list[dict]:
    from shadow.world.executable import compile_primitives

    rows = []
    for case in cases:
        compiled = compile_primitives(case["plan"], [{"id": "user", "text": case["text"], "observed_at": ""}])
        rows.append(
            {
                "id": case["id"],
                "status": compiled.status,
                "constraints": compiled.constraint_labels,
                "missing": compiled.missing,
                "contradictions": compiled.contradictions,
            }
        )
    return rows


def _live(cases: list[dict]) -> dict:
    from pydantic import ValidationError

    from shadow.llm.budget import BudgetError, BudgetLedger
    from shadow.llm.client import LiveDisabled, ResponseCache, SchemaError, model_client, prompt_hash
    from shadow.world.executable import ExecutableProposal, validate_proposal

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
    for case in cases:
        records = [{"id": "user", "text": case["text"]}]
        context = {"plan_text": case["plan"], "records": records}
        before = float(ledger.snapshot()["repo_actual_spend_usd"])
        try:
            proposal = client.complete_json("compile_executable", context, ExecutableProposal, model=SUPER)
        except BudgetError:
            raise
        except (SchemaError, ValidationError, LiveDisabled) as exc:
            rows.append({"id": case["id"], "schema_ok": False, "error": str(exc)[:500]})
            continue
        spent = float(ledger.snapshot()["repo_actual_spend_usd"]) - before
        checked = validate_proposal(proposal, records)
        rows.append(
            {
                "id": case["id"],
                "schema_ok": True,
                "cost_usd": round(max(0.0, spent), 8),
                "validation": checked.status,
                "reason": checked.reason,
                "rejected": checked.rejected[:8],
                "constraints": [item.label for item in proposal.constraints],
                "variables": [item.model_dump(mode="json") for item in proposal.variables],
                "actions": [item.id for item in proposal.actions],
            }
        )
    after = float(ledger.snapshot()["repo_actual_spend_usd"])
    return {
        "model": SUPER,
        "prompt_hash": prompt_hash("compile_executable.txt"),
        "cost_usd": round(after - baseline, 8),
        "rows": rows,
    }


def main() -> None:
    digest = _freeze()
    cases = json.loads(CASES.read_text())
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "grammar":
        print(json.dumps({"dataset_hash": digest, "rows": _grammar(cases)}, indent=2))
        return
    if (OUT / "live.json").exists():
        raise SystemExit("semantic explore live pass already recorded")
    payload = {"dataset_hash": digest, "grammar": _grammar(cases), "live": _live(cases)}
    (OUT / "live.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"cost": payload["live"]["cost_usd"], "schema": [row.get("schema_ok") for row in payload["live"]["rows"]]}))


if __name__ == "__main__":
    main()
