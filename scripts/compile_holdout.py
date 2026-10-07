"""One Lightning compile call per frozen holdout case. Stops before the extra $0.02 cap."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from pydantic import ValidationError  # noqa: E402

from shadow.llm.budget import BudgetError, BudgetLedger  # noqa: E402
from shadow.llm.client import ResponseCache, SchemaError, model_client  # noqa: E402
from shadow.world.compiler import SemanticProposal, proposal_from_payload, score_compilation  # noqa: E402

HOLD = ROOT / "shadowbench" / "world_compiler_holdout"
CAP = 0.02


def main() -> None:
    cases = json.loads((HOLD / "cases.json").read_text())
    oracle = json.loads((HOLD / "oracle.json").read_text())
    ledger = BudgetLedger(ROOT / "data" / "budget.json")
    baseline = float(ledger.snapshot()["repo_actual_spend_usd"])
    os.environ["SHADOW_SESSION_BASELINE_USD"] = f"{baseline:.8f}"
    os.environ["SHADOW_SESSION_CAP_USD"] = f"{CAP:.2f}"
    os.environ["NEBIUS_LIVE"] = "1"
    os.environ.pop("ALLOW_SUPER", None)
    os.environ.pop("ALLOW_ULTRA", None)
    client = model_client(ledger, ResponseCache(ROOT / "data" / "cache.sqlite"))
    rows = []
    for case in cases:
        spent = float(ledger.snapshot()["repo_actual_spend_usd"]) - baseline
        if spent >= CAP:
            break
        context = {"plan_text": case["plan_text"], "records": case["records"]}
        try:
            proposal = client.complete_json("compile_world", context, SemanticProposal)
        except BudgetError:
            break
        except (SchemaError, ValidationError):
            spec = oracle[case["id"]]
            rows.append({"id": case["id"], "error": "schema", "hard_hit": 0, "hard_total": len(spec.get("hard") or []), "false_hard": 0, "hard_proposed": 0, "dep_hit": 0, "dep_total": len(spec.get("dependencies") or []), "false_dep": 0, "dep_proposed": 0, "unknown_hit": 0, "unknown_total": len(spec.get("unknowns") or []), "provenance_hit": 0, "provenance_total": 0, "repair_ok": False, "repair_applicable": spec.get("repair") is not None})
            continue
        compiled_payload = proposal_from_payload(proposal.model_dump())
        from shadow.world.compiler import CompiledWorld, _item
        from shadow.core.models import EpistemicStatus

        world = CompiledWorld()
        for index, row in enumerate(compiled_payload.hard_constraints):
            world.hard_constraints.append(
                _item(
                    f"h{index}",
                    "hard_constraint",
                    str(row.get("label") or ""),
                    EpistemicStatus.INFERRED,
                    [str(item) for item in row.get("source_ids") or []],
                    "model",
                    False,
                )
            )
        for index, row in enumerate(compiled_payload.dependencies):
            world.dependencies.append(
                _item(
                    f"d{index}",
                    "dependency",
                    str(row.get("label") or ""),
                    EpistemicStatus.INFERRED,
                    [str(item) for item in row.get("source_ids") or []],
                    "model",
                    False,
                )
            )
        for index, row in enumerate(compiled_payload.unknowns):
            world.unknowns.append(
                _item(
                    f"u{index}",
                    "unknown",
                    str(row.get("label") or ""),
                    EpistemicStatus.UNKNOWN,
                    [str(item) for item in row.get("source_ids") or []],
                    "model",
                    True,
                )
            )
        scored = score_compilation(world, oracle[case["id"]])
        scored["id"] = case["id"]
        rows.append(scored)
    spent = float(ledger.snapshot()["repo_actual_spend_usd"]) - baseline
    totals = {
        "cases": len(rows),
        "hard_hit": sum(row["hard_hit"] for row in rows),
        "hard_total": sum(row["hard_total"] for row in rows),
        "false_hard": sum(row["false_hard"] for row in rows),
        "hard_proposed": sum(row["hard_proposed"] for row in rows),
        "dep_hit": sum(row["dep_hit"] for row in rows),
        "dep_total": sum(row["dep_total"] for row in rows),
        "false_dep": sum(row["false_dep"] for row in rows),
        "dep_proposed": sum(row["dep_proposed"] for row in rows),
        "unknown_hit": sum(row["unknown_hit"] for row in rows),
        "unknown_total": sum(row["unknown_total"] for row in rows),
        "provenance_hit": sum(row["provenance_hit"] for row in rows),
        "provenance_total": sum(row["provenance_total"] for row in rows),
        "repair_ok": sum(1 for row in rows if row["repair_ok"]),
        "repair_total": sum(1 for row in rows if row["repair_applicable"]),
        "additional_spend_usd": round(spent, 8),
        "rows": rows,
    }
    (HOLD / "results.json").write_text(json.dumps(totals, indent=2))
    print(json.dumps({key: totals[key] for key in totals if key != "rows"}))


if __name__ == "__main__":
    main()
