"""Choose a compile route on frozen development cases, then score that route once on holdout."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from pydantic import ValidationError  # noqa: E402

from shadow.llm.budget import BudgetError, BudgetLedger  # noqa: E402
from shadow.llm.client import LiveDisabled, ResponseCache, SchemaError, model_client  # noqa: E402
from shadow.world.compiler import (  # noqa: E402
    SemanticProposal,
    proposal_from_payload,
    score_compilation,
    verify_proposal,
    world_from_proposal,
)

PROTOCOL = json.loads((ROOT / "shadowbench" / "routing" / "protocol.json").read_text())
DEV = ROOT / "shadowbench" / "routing_dev"
HOLD = ROOT / "shadowbench" / "routing_holdout"
DECISION = ROOT / "shadowbench" / "routing" / "decision.json"


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if mode == "dev":
        if DECISION.exists():
            raise SystemExit("decision already frozen")
        _run_dev()
    elif mode == "holdout":
        if not DECISION.exists():
            raise SystemExit("freeze a winner before holdout")
        if (HOLD / "results.json").exists():
            raise SystemExit("holdout already scored")
        _run_holdout()
    else:
        raise SystemExit("mode must be dev or holdout")


def _run_dev() -> None:
    cases = json.loads((DEV / "cases.json").read_text())
    oracle = json.loads((DEV / "oracle.json").read_text())
    client, ledger, baseline = _client()
    lightning_rows = []
    super_rows = []
    lightning_spend = 0.0
    super_spend = 0.0
    for case in cases:
        light, light_cost = _call(client, ledger, baseline, case, PROTOCOL["models"]["lightning"])
        lightning_spend += light_cost
        lightning_rows.append(_score(case, oracle, light, verified=False))
        verified = verify_proposal(case, light) if light is not None else world_from_proposal(SemanticProposal())
        lightning_rows[-1]  # raw lightning already stored
        super_proposal, super_cost = _call(client, ledger, baseline, case, PROTOCOL["models"]["super"])
        super_spend += super_cost
        super_rows.append(_score(case, oracle, super_proposal, verified=False))
        lightning_rows[-1]["verified"] = score_compilation(verified, oracle[case["id"]])
    summaries = {
        "lightning": _aggregate(lightning_rows, lightning_spend, key=None),
        "super": _aggregate(super_rows, super_spend, key=None),
        "compiler_verifier": _aggregate(lightning_rows, lightning_spend, key="verified"),
    }
    winner = _select(summaries)
    payload = {"winner": winner, "summaries": summaries, "protocol": PROTOCOL}
    (DEV / "results.json").write_text(json.dumps(payload, indent=2))
    DECISION.write_text(json.dumps({"system": winner, "model": PROTOCOL["models"][winner], "dev_results": "shadowbench/routing_dev/results.json"}, indent=2) + "\n")
    print(json.dumps({"winner": winner, "summaries": {name: _public(item) for name, item in summaries.items()}}))


def _run_holdout() -> None:
    decision = json.loads(DECISION.read_text())
    system = decision["system"]
    cases = json.loads((HOLD / "cases.json").read_text())
    oracle = json.loads((HOLD / "oracle.json").read_text())
    client, ledger, baseline = _client()
    rows = []
    spend = 0.0
    model = PROTOCOL["models"]["lightning" if system == "compiler_verifier" else system]
    for case in cases:
        proposal, cost = _call(client, ledger, baseline, case, model)
        spend += cost
        if system == "compiler_verifier" and proposal is not None:
            compiled_score = score_compilation(verify_proposal(case, proposal), oracle[case["id"]])
        else:
            compiled_score = _score(case, oracle, proposal, verified=False)
            compiled_score = {key: compiled_score[key] for key in compiled_score if key != "id"}
        compiled_score["id"] = case["id"]
        rows.append(compiled_score)
    summary = _aggregate(rows, spend, key=None if system != "compiler_verifier" else None)
    if system == "compiler_verifier":
        summary = _aggregate([{"verified": row, "id": row["id"]} for row in rows], spend, key="verified")
    out = {"system": system, "summary": summary, "once": True}
    (HOLD / "results.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({"system": system, "summary": _public(summary)}))


def _score(case: dict, oracle: dict, proposal: SemanticProposal | None, verified: bool) -> dict:
    if proposal is None:
        scored = score_compilation(world_from_proposal(SemanticProposal()), oracle[case["id"]])
    else:
        scored = score_compilation(world_from_proposal(proposal), oracle[case["id"]])
    scored["id"] = case["id"]
    return scored


def _call(client, ledger, baseline: float, case: dict, model: str):
    before = float(ledger.snapshot()["repo_actual_spend_usd"])
    context = {"plan_text": case["plan_text"], "records": case["records"]}
    try:
        proposal = client.complete_json("compile_world", context, SemanticProposal, model=model)
    except BudgetError:
        raise
    except (SchemaError, ValidationError, LiveDisabled):
        proposal = None
    after = float(ledger.snapshot()["repo_actual_spend_usd"])
    return proposal, max(0.0, after - before)


def _aggregate(rows: list[dict], spend: float, key: str | None) -> dict:
    picked = [row[key] if key else row for row in rows]
    repair_ok = sum(1 for row in picked if row.get("repair_ok"))
    repair_total = sum(1 for row in picked if row.get("repair_applicable"))
    hard_hit = sum(row["hard_hit"] for row in picked)
    hard_total = sum(row["hard_total"] for row in picked)
    false_hard = sum(row["false_hard"] for row in picked)
    hard_proposed = sum(row["hard_proposed"] for row in picked)
    unknown_hit = sum(row["unknown_hit"] for row in picked)
    unknown_total = sum(row["unknown_total"] for row in picked)
    return {
        "cases": len(picked),
        "hard_hit": hard_hit,
        "hard_total": hard_total,
        "false_hard": false_hard,
        "hard_proposed": hard_proposed,
        "dep_hit": sum(row["dep_hit"] for row in picked),
        "dep_total": sum(row["dep_total"] for row in picked),
        "false_dep": sum(row["false_dep"] for row in picked),
        "dep_proposed": sum(row["dep_proposed"] for row in picked),
        "unknown_hit": unknown_hit,
        "unknown_total": unknown_total,
        "provenance_hit": sum(row["provenance_hit"] for row in picked),
        "provenance_total": sum(row["provenance_total"] for row in picked),
        "repair_ok": repair_ok,
        "repair_total": repair_total,
        "repair_rate": _rate(repair_ok, repair_total),
        "hard_recall": _rate(hard_hit, hard_total),
        "false_hard_rate": _rate(false_hard, hard_proposed),
        "unknown_rate": _rate(unknown_hit, unknown_total),
        "cost_usd": round(spend, 8),
        "rows": picked,
    }


def _select(summaries: dict) -> str:
    def sort_key(name: str):
        item = summaries[name]
        return (
            item["repair_rate"],
            item["hard_recall"],
            -item["false_hard_rate"],
            item["unknown_rate"],
            -item["cost_usd"],
            -PROTOCOL["tie_break"].index(name),
        )

    return max(summaries, key=sort_key)


def _public(item: dict) -> dict:
    return {key: value for key, value in item.items() if key != "rows"}


def _rate(hit: float, total: float) -> float:
    return 0.0 if not total else hit / total


def _client():
    ledger = BudgetLedger(ROOT / "data" / "budget.json")
    baseline = float(ledger.snapshot()["repo_actual_spend_usd"])
    os.environ["SHADOW_SESSION_BASELINE_USD"] = f"{baseline:.8f}"
    os.environ["SHADOW_SESSION_CAP_USD"] = str(PROTOCOL["dev_session_cap_usd"])
    os.environ["NEBIUS_LIVE"] = "1"
    os.environ["ALLOW_SUPER"] = "true"
    os.environ.pop("ALLOW_ULTRA", None)
    os.environ.pop("NEBIUS_MODEL", None)
    client = model_client(ledger, ResponseCache(ROOT / "data" / "cache.sqlite"))
    return client, ledger, baseline


if __name__ == "__main__":
    main()
