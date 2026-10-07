"""Score the generic compiler on a frozen attack set. Does not edit older studies."""

from __future__ import annotations

import hashlib
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
    compile_bundle,
    score_compilation,
    verify_proposal,
)
from shadow.world.example_world import license_example_bundle  # noqa: E402

STUDY = ROOT / "shadowbench" / "redteam-compiler"
CASES = STUDY / "cases.json"
ORACLE = STUDY / "oracle.json"
FROZEN = STUDY / "FROZEN.sha256"
SUPER = "nvidia/nemotron-3-super-120b-a12b"


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "rules"
    if mode == "rules":
        _check_frozen()
        payload = _rules()
        print(json.dumps({name: {key: value for key, value in item.items() if key != "rows"} for name, item in payload.items()}))
    elif mode == "live":
        if (STUDY / "live.json").exists():
            raise SystemExit("red-team live split already scored")
        _check_frozen()
        print(json.dumps(_live(), indent=2))
    else:
        raise SystemExit("mode must be rules or live")


def _rules() -> dict:
    cases, oracle = _load()
    rows = [_score(case, oracle, compile_bundle(case)) for case in cases]
    example_rows = [_score(case, oracle, license_example_bundle(case)) for case in cases]
    payload = {"rules_only": _aggregate(rows, 0.0), "example_adapter": _aggregate(example_rows, 0.0)}
    (STUDY / "rules.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def _live() -> dict:
    cases, oracle = _load()
    client, ledger, baseline = _client()
    rows = []
    spend = 0.0
    for case in cases:
        before = float(ledger.snapshot()["repo_actual_spend_usd"])
        try:
            proposal = client.complete_json("compile_world", {"plan_text": case["plan_text"], "records": case["records"]}, SemanticProposal, model=SUPER)
        except BudgetError:
            raise
        except (SchemaError, ValidationError, LiveDisabled):
            proposal = None
        spend += max(0.0, float(ledger.snapshot()["repo_actual_spend_usd"]) - before)
        world = verify_proposal(case, proposal or SemanticProposal())
        rows.append(_score(case, oracle, world))
    summary = _aggregate(rows, spend)
    payload = {"architecture": "super_plus_verifier", "summary": summary, "once": True, "git": "redteam"}
    (STUDY / "live.json").write_text(json.dumps(payload, indent=2) + "\n")
    return {key: value for key, value in summary.items() if key != "rows"}


def _score(case: dict, oracle: dict, world) -> dict:
    scored = score_compilation(world, oracle[case["id"]])
    scored["id"] = case["id"]
    labels = " ".join(item.label.lower() for item in world.items())
    scored["contradiction_hit"] = (not oracle[case["id"]].get("contradiction")) or ("contradict" in labels or "conflict" in labels)
    return scored


def _aggregate(rows: list[dict], spend: float) -> dict:
    contradictions = [row for row in rows if json.loads(ORACLE.read_text())[row["id"]].get("contradiction")]
    return {
        "cases": len(rows),
        "hard_hit": sum(row["hard_hit"] for row in rows),
        "hard_total": sum(row["hard_total"] for row in rows),
        "false_hard": sum(row["false_hard"] for row in rows),
        "hard_proposed": sum(row["hard_proposed"] for row in rows),
        "dep_hit": sum(row["dep_hit"] for row in rows),
        "dep_total": sum(row["dep_total"] for row in rows),
        "false_dep": sum(row["false_dep"] for row in rows),
        "unknown_hit": sum(row["unknown_hit"] for row in rows),
        "unknown_total": sum(row["unknown_total"] for row in rows),
        "provenance_hit": sum(row["provenance_hit"] for row in rows),
        "provenance_total": sum(row["provenance_total"] for row in rows),
        "repair_ok": sum(1 for row in rows if row.get("repair_ok")),
        "repair_total": sum(1 for row in rows if row.get("repair_applicable")),
        "contradiction_hit": sum(1 for row in contradictions if row["contradiction_hit"]),
        "contradiction_total": len(contradictions),
        "hard_recall": _rate(sum(row["hard_hit"] for row in rows), sum(row["hard_total"] for row in rows)),
        "false_hard_rate": _rate(sum(row["false_hard"] for row in rows), sum(row["hard_proposed"] for row in rows)),
        "dependency_recall": _rate(sum(row["dep_hit"] for row in rows), sum(row["dep_total"] for row in rows)),
        "unknown_rate": _rate(sum(row["unknown_hit"] for row in rows), sum(row["unknown_total"] for row in rows)),
        "provenance_coverage": _rate(sum(row["provenance_hit"] for row in rows), sum(row["provenance_total"] for row in rows)),
        "repair_rate": _rate(sum(1 for row in rows if row.get("repair_ok")), sum(1 for row in rows if row.get("repair_applicable"))),
        "cost_usd": round(spend, 8),
        "rows": rows,
    }


def _load() -> tuple[list, dict]:
    return json.loads(CASES.read_text()), json.loads(ORACLE.read_text())


def _check_frozen() -> None:
    digest = hashlib.sha256(CASES.read_bytes() + ORACLE.read_bytes()).hexdigest()
    if not FROZEN.exists():
        FROZEN.write_text(digest + "\n")
        return
    if FROZEN.read_text().strip() != digest:
        raise SystemExit("red-team compiler set changed after it was frozen")


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
    os.environ["SHADOW_SESSION_CAP_USD"] = "0.15"
    os.environ["NEBIUS_LIVE"] = "1"
    os.environ["ALLOW_SUPER"] = "true"
    os.environ.pop("ALLOW_ULTRA", None)
    return model_client(ledger, ResponseCache(ROOT / "data" / "cache.sqlite")), ledger, baseline


if __name__ == "__main__":
    main()
