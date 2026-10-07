"""Compare four compiler architectures. Does not touch frozen routing results."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from pydantic import BaseModel  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from shadow.llm.budget import BudgetError, BudgetLedger  # noqa: E402
from shadow.llm.client import LiveDisabled, ResponseCache, SchemaError, model_client  # noqa: E402
from shadow.world.compiler import (  # noqa: E402
    AuditReport,
    SemanticProposal,
    merge_audit,
    score_compilation,
    world_from_proposal,
)
from shadow.world.routing import select_architecture  # noqa: E402

STUDY = ROOT / "shadowbench" / "compiler-study"
DEV = STUDY / "dev"
TEST = STUDY / "test"
DECISION = STUDY / "decision.json"
FROZEN = TEST / "FROZEN.sha256"
LIGHTNING = "nvidia/Nemotron-3_5-Lightning"
SUPER = "nvidia/nemotron-3-super-120b-a12b"
ARCHITECTURES = ("lightning", "lightning_audit", "super", "super_audit")
PASS_CAP_USD = 0.20


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "probe":
        _probe()
    elif mode == "dev":
        if DECISION.exists():
            raise SystemExit("compiler study decision already frozen")
        _freeze_test()
        _dev()
    elif mode == "test":
        if not DECISION.exists():
            raise SystemExit("freeze a compiler architecture before the test split")
        if (TEST / "results.json").exists():
            raise SystemExit("compiler test split already scored")
        _check_frozen()
        _test()
    else:
        raise SystemExit("mode must be probe, dev, or test")


def _probe() -> None:
    _freeze_test()
    cases = json.loads((DEV / "cases.json").read_text())[:5]
    oracle = json.loads((DEV / "oracle.json").read_text())
    client, ledger, baseline = _client()
    spend = 0.0
    for case in cases:
        for architecture in ARCHITECTURES:
            _world, cost, _stats = _run(client, ledger, baseline, case, architecture)
            spend += cost
    projected = spend / max(len(cases), 1) * 32
    print(json.dumps({"probe_cases": len(cases), "probe_spend_usd": round(spend, 8), "projected_dev_usd": round(projected, 8)}))
    if projected > 3:
        raise SystemExit("projected compiler study exceeds $3")


def _dev() -> None:
    cases = json.loads((DEV / "cases.json").read_text())
    oracle = json.loads((DEV / "oracle.json").read_text())
    client, ledger, baseline = _client()
    buckets = {name: [] for name in ARCHITECTURES}
    spend = {name: 0.0 for name in ARCHITECTURES}
    usage = {name: _blank_usage() for name in ARCHITECTURES}
    for case in cases:
        for architecture in ARCHITECTURES:
            world, cost, stats = _run(client, ledger, baseline, case, architecture)
            spend[architecture] += cost
            _add_usage(usage[architecture], stats)
            buckets[architecture].append(_score(case, oracle, world))
    summaries = {
        name: _aggregate(buckets[name], spend[name], usage[name]) for name in ARCHITECTURES
    }
    # Audit runs reuse the cached compile call, so add that shared cost before the tie-break.
    for audited, base in (("lightning_audit", "lightning"), ("super_audit", "super")):
        summaries[audited]["measured_cost_usd"] = summaries[audited]["cost_usd"]
        summaries[base]["measured_cost_usd"] = summaries[base]["cost_usd"]
        summaries[audited]["cost_usd"] = round(summaries[base]["cost_usd"] + summaries[audited]["measured_cost_usd"], 8)
    winner = select_architecture(summaries)
    payload = {
        "winner": winner,
        "rationale": _rationale(winner, summaries),
        "summaries": summaries,
        "selection": [
            "false_hard_rate within 0.05 of the best",
            "hard_recall",
            "unknown_rate",
            "repair_rate",
            "lower cost",
        ],
    }
    (DEV / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    DECISION.write_text(
        json.dumps(
            {
                "architecture": winner,
                "compile_model": SUPER if winner.startswith("super") else LIGHTNING,
                "audit_model": LIGHTNING if winner.endswith("audit") else None,
                "dev_results": "shadowbench/compiler-study/dev/results.json",
                "rationale": payload["rationale"],
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"winner": winner, "summaries": {name: _public(item) for name, item in summaries.items()}}))


def _test() -> None:
    decision = json.loads(DECISION.read_text())
    architecture = decision["architecture"]
    cases = json.loads((TEST / "cases.json").read_text())
    oracle = json.loads((TEST / "oracle.json").read_text())
    client, ledger, baseline = _client()
    rows = []
    spend = 0.0
    usage = _blank_usage()
    for case in cases:
        world, cost, stats = _run(client, ledger, baseline, case, architecture)
        spend += cost
        _add_usage(usage, stats)
        rows.append(_score(case, oracle, world))
    summary = _aggregate(rows, spend, usage)
    out = {"architecture": architecture, "summary": summary, "once": True}
    (TEST / "results.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"architecture": architecture, "summary": _public(summary)}))


def _run(client, ledger, baseline: float, case: dict, architecture: str):
    context = {"plan_text": case["plan_text"], "records": case["records"]}
    compile_model = SUPER if architecture.startswith("super") else LIGHTNING
    proposal, stats = _call(client, ledger, baseline, "compile_world", context, SemanticProposal, compile_model)
    world = world_from_proposal(proposal if proposal is not None else SemanticProposal())
    if architecture.endswith("_audit"):
        audit_context = {
            "plan_text": case["plan_text"],
            "records": case["records"],
            "compiled": {
                "hard_constraints": [item.label for item in world.hard_constraints],
                "soft_preferences": [item.label for item in world.soft_preferences],
                "dependencies": [item.label for item in world.dependencies],
                "unknowns": [item.label for item in world.unknowns],
            },
        }
        report, audit_stats = _call(client, ledger, baseline, "audit_world", audit_context, AuditReport, LIGHTNING)
        stats = _merge_stats(stats, audit_stats)
        if isinstance(report, AuditReport):
            records = {str(item["id"]): str(item["text"]) for item in case["records"]}
            world = merge_audit(world, report, records)
    return world, stats["cost_usd"], stats


def _call(client, ledger, baseline: float, purpose: str, context: dict, schema: type[BaseModel], model: str):
    before = float(ledger.snapshot()["repo_actual_spend_usd"])
    calls_before = len(client.calls)
    try:
        parsed = client.complete_json(purpose, context, schema, model=model)
    except BudgetError:
        raise
    except (SchemaError, ValidationError, LiveDisabled):
        parsed = None
    after = float(ledger.snapshot()["repo_actual_spend_usd"])
    fresh = client.calls[calls_before:]
    return parsed, {
        "cost_usd": max(0.0, after - before),
        "calls": len(fresh),
        "input_tokens": sum(int(item.get("input_tokens") or 0) for item in fresh),
        "output_tokens": sum(int(item.get("output_tokens") or 0) for item in fresh),
        "latency_s": sum(float(item.get("latency_s") or 0) for item in fresh),
    }


def _score(case: dict, oracle: dict, world) -> dict:
    scored = score_compilation(world, oracle[case["id"]])
    scored["id"] = case["id"]
    scored["contradiction_hit"] = _contradiction(world, oracle[case["id"]])
    scored["contradiction_applicable"] = bool(oracle[case["id"]].get("contradiction"))
    return scored


def _contradiction(world, oracle: dict) -> bool | None:
    if not oracle.get("contradiction"):
        return None
    labels = " ".join(item.label.lower() for item in world.items())
    return "contradict" in labels or "conflict" in labels


def _aggregate(rows: list[dict], spend: float, usage: dict) -> dict:
    repair_ok = sum(1 for row in rows if row.get("repair_ok"))
    repair_total = sum(1 for row in rows if row.get("repair_applicable"))
    hard_hit = sum(row["hard_hit"] for row in rows)
    hard_total = sum(row["hard_total"] for row in rows)
    false_hard = sum(row["false_hard"] for row in rows)
    hard_proposed = sum(row["hard_proposed"] for row in rows)
    contradictions = [row["contradiction_hit"] for row in rows if row["contradiction_applicable"]]
    return {
        "cases": len(rows),
        "hard_hit": hard_hit,
        "hard_total": hard_total,
        "false_hard": false_hard,
        "hard_proposed": hard_proposed,
        "dep_hit": sum(row["dep_hit"] for row in rows),
        "dep_total": sum(row["dep_total"] for row in rows),
        "false_dep": sum(row["false_dep"] for row in rows),
        "dep_proposed": sum(row["dep_proposed"] for row in rows),
        "unknown_hit": sum(row["unknown_hit"] for row in rows),
        "unknown_total": sum(row["unknown_total"] for row in rows),
        "provenance_hit": sum(row["provenance_hit"] for row in rows),
        "provenance_total": sum(row["provenance_total"] for row in rows),
        "contradiction_hit": sum(1 for item in contradictions if item),
        "contradiction_total": len(contradictions),
        "repair_ok": repair_ok,
        "repair_total": repair_total,
        "repair_rate": _rate(repair_ok, repair_total),
        "hard_recall": _rate(hard_hit, hard_total),
        "false_hard_rate": _rate(false_hard, hard_proposed),
        "unknown_rate": _rate(sum(row["unknown_hit"] for row in rows), sum(row["unknown_total"] for row in rows)),
        "dependency_recall": _rate(sum(row["dep_hit"] for row in rows), sum(row["dep_total"] for row in rows)),
        "false_dependency_rate": _rate(sum(row["false_dep"] for row in rows), sum(row["dep_proposed"] for row in rows)),
        "provenance_coverage": _rate(sum(row["provenance_hit"] for row in rows), sum(row["provenance_total"] for row in rows)),
        "contradiction_detection_rate": _rate(sum(1 for item in contradictions if item), len(contradictions)),
        "cost_usd": round(spend, 8),
        "model_calls": usage["calls"],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "latency_s": round(usage["latency_s"], 3),
        "rows": rows,
    }


def _rationale(winner: str, summaries: dict) -> str:
    item = summaries[winner]
    return (
        f"{winner} won because its false hard-constraint rate stayed with the best group "
        f"({item['false_hard_rate']:.2f}) while hard recall was {item['hard_recall']:.2f}, "
        f"unknown preservation was {item['unknown_rate']:.2f}, and repair success was {item['repair_rate']:.2f}."
    )


def _blank_usage() -> dict:
    return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_s": 0.0}


def _add_usage(total: dict, stats: dict) -> None:
    total["calls"] += stats["calls"]
    total["input_tokens"] += stats["input_tokens"]
    total["output_tokens"] += stats["output_tokens"]
    total["latency_s"] += stats["latency_s"]


def _merge_stats(left: dict, right: dict) -> dict:
    return {
        "cost_usd": left["cost_usd"] + right["cost_usd"],
        "calls": left["calls"] + right["calls"],
        "input_tokens": left["input_tokens"] + right["input_tokens"],
        "output_tokens": left["output_tokens"] + right["output_tokens"],
        "latency_s": left["latency_s"] + right["latency_s"],
    }


def _freeze_test() -> None:
    if FROZEN.exists():
        _check_frozen()
        return
    digest = _test_hash()
    FROZEN.write_text(digest + "\n")


def _check_frozen() -> None:
    if not FROZEN.exists():
        raise SystemExit("test split was not frozen")
    if FROZEN.read_text().strip() != _test_hash():
        raise SystemExit("test split changed after it was frozen")


def _test_hash() -> str:
    payload = (TEST / "cases.json").read_bytes() + (TEST / "oracle.json").read_bytes()
    return hashlib.sha256(payload).hexdigest()


def _public(item: dict) -> dict:
    return {key: value for key, value in item.items() if key != "rows"}


def _rate(hit: float, total: float) -> float:
    return 0.0 if not total else hit / total


def _load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _client():
    _load_env()
    ledger = BudgetLedger(ROOT / "data" / "budget.json")
    baseline = float(ledger.snapshot()["repo_actual_spend_usd"])
    os.environ["SHADOW_SESSION_BASELINE_USD"] = f"{baseline:.8f}"
    os.environ["SHADOW_SESSION_CAP_USD"] = str(PASS_CAP_USD)
    os.environ["NEBIUS_LIVE"] = "1"
    os.environ["ALLOW_SUPER"] = "true"
    os.environ.pop("ALLOW_ULTRA", None)
    os.environ.pop("NEBIUS_MODEL", None)
    client = model_client(ledger, ResponseCache(ROOT / "data" / "cache.sqlite"))
    return client, ledger, baseline


if __name__ == "__main__":
    main()
