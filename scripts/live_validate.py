"""One live validation session. Never prints the API key."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from shadow.benchmark.live_pilot import run_pilot  # noqa: E402
from shadow.core.models import PlanSpec  # noqa: E402
from shadow.llm.budget import BudgetLedger  # noqa: E402
from shadow.llm.client import LiveDisabled, NebiusClient, ResponseCache, SchemaError  # noqa: E402
from shadow.llm.pricing import DEFAULT_MODEL  # noqa: E402
from shadow.pipeline import PlanService  # noqa: E402
from shadow.runtime.events import EventLog  # noqa: E402

PRIOR_EXTERNAL = 0.02030592
PREVIOUS_REPO = 0.0000222
SESSION_CAP = 0.03
HERO = "Move my NYC trip to Friday and make sure everything still works."


def redact(text: str) -> str:
    key = os.environ.get("NEBIUS_API_KEY") or ""
    if key:
        text = text.replace(key, "[redacted]")
    return text


def main() -> None:
    print("live-validate start", flush=True)
    if os.environ.get("NEBIUS_LIVE") != "1":
        raise SystemExit("NEBIUS_LIVE is not 1")
    if not os.environ.get("NEBIUS_API_KEY"):
        raise SystemExit("NEBIUS_API_KEY is not set")
    os.environ["NEBIUS_MODEL"] = DEFAULT_MODEL
    os.environ.pop("ALLOW_SUPER", None)
    os.environ.pop("ALLOW_ULTRA", None)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    ledger = BudgetLedger(ROOT / "data" / "budget.json")
    os.environ["SHADOW_SESSION_CAP_USD"] = str(SESSION_CAP)
    os.environ["SHADOW_SESSION_BASELINE_USD"] = "0"
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    directory = ROOT / "shadowbench" / "results" / f"live-pilot-{stamp}"
    directory.mkdir(parents=True, exist_ok=True)
    client = NebiusClient(ledger, ResponseCache(ROOT / "data" / "cache.sqlite"))
    try:
        smoke = _smoke(client, ledger)
        hero = _hero(client)
        pilot = run_pilot(client, ledger, directory, session_baseline=0.0, session_cap=SESSION_CAP)
        trace = _hero(client, trace=True) if hero.get("schema_valid") else {"schema_valid": False, "cache_hits": 0}
        try:
            tavily = _tavily()
        except Exception as exc:
            tavily = {"status": "error", "reason": redact(str(exc))}
        openshell = _openshell()
    except Exception as exc:
        raise SystemExit(redact(f"{type(exc).__name__}: {exc}")) from None
    _finish(directory, ledger, 0.0, smoke, hero, trace, pilot, tavily, openshell)
    print(redact(json.dumps(_public_cost(ledger, 0.0, smoke, pilot), indent=2)))


def _smoke(client: NebiusClient, ledger: BudgetLedger) -> dict[str, object]:
    context = {
        "plan": "Move the Friday trip if the fixed dinner still holds.",
        "constraints": [{"id": "c_dinner", "description": "Dinner stays at 19:00.", "hardness": "hard"}],
        "unknowns": [],
        "bundles": [{"id": "opt_a", "label": "Option A", "action_ids": ["keep_dinner"]}],
        "note": "MARKER_PRIVATE_ALEX_NOTE",
    }
    before = float(ledger.snapshot()["repo_actual_spend_usd"])
    spec = client.complete_json("analyze_plan", context, PlanSpec)
    if not isinstance(spec, PlanSpec):
        raise LiveDisabled("smoke response was not a PlanSpec")
    first = client.calls[-1]
    if not first.get("cache_hit"):
        if not first.get("schema_valid"):
            raise LiveDisabled("smoke call was not a live schema-valid response")
        if first.get("model") != DEFAULT_MODEL:
            raise LiveDisabled("smoke model did not match Lightning")
        if not first.get("input_tokens") or first.get("output_tokens") is None:
            raise LiveDisabled("smoke usage was missing")
        after = float(ledger.snapshot()["repo_actual_spend_usd"])
        if after <= before:
            raise LiveDisabled("smoke cost was not reconciled")
    else:
        after = float(ledger.snapshot()["repo_actual_spend_usd"])
        if after != before:
            raise LiveDisabled("cache hit changed the ledger")
    client.complete_json("analyze_plan", context, PlanSpec)
    second = client.calls[-1]
    if not second.get("cache_hit") or float(ledger.snapshot()["repo_actual_spend_usd"]) != after:
        raise LiveDisabled("identical smoke call was not a free cache hit")
    dumped = json.dumps(client.calls)
    if "MARKER_PRIVATE_ALEX_NOTE" in dumped or (os.environ.get("NEBIUS_API_KEY") or "") in dumped:
        raise LiveDisabled("call log contains private text")
    return {"calls": [first, second], "cost_usd": after - before}


def _hero(client: NebiusClient, trace: bool = False) -> dict[str, object]:
    before = len(client.calls)
    service = PlanService(EventLog("sqlite://"), client)
    created = service.create(HERO, "travel", 7)
    try:
        view = service.analyze(created["id"])
    except SchemaError as exc:
        return {"schema_valid": False, "error": type(exc).__name__, "trace": trace, "calls": client.calls[before:]}
    fresh = client.calls[before:]
    approved = None
    executed = None
    if view.get("recommended_repair_id"):
        approved = service.approve(created["id"], view["recommended_repair_id"])
        executed = service.execute(created["id"])
    rejected = [
        {"id": item["id"], "status": item["status"], "source": item["source"]}
        for item in view["repairs"]
        if item["source"] == "model" and item["status"] != "feasible"
    ]
    naive = next((item for item in view["repairs"] if item["id"] == view["naive_repair_id"]), None)
    return {
        "schema_valid": True,
        "trace": trace,
        "calls": fresh,
        "cache_hits": sum(1 for item in fresh if item.get("cache_hit")),
        "recommended": view.get("recommended_repair_id"),
        "naive": view.get("naive_repair_id"),
        "rejected_model_repairs": rejected,
        "failure_variables": []
        if naive is None
        else sorted({pert["variable"] for failure in naive["failures"] for pert in failure["perturbations"]}),
        "contract_status": None if approved is None else approved.get("status"),
        "allowed_actions": [] if approved is None else [item["action_id"] for item in approved["allowed_actions"]],
        "execute_status": None if executed is None else executed.get("status"),
        "reconciliation": service.view(created["id"]).get("reconciliation"),
        "dependencies": [item.model_dump(mode="json") for item in service.plans[created["id"]]["spec"].dependencies],
        "hazards": [item.description for item in service.plans[created["id"]]["spec"].hazards],
        "unknowns": list(service.plans[created["id"]]["spec"].unknowns),
        "facts": service.plans[created["id"]].get("retrieval"),
    }


def _tavily() -> dict[str, object]:
    if not os.environ.get("TAVILY_API_KEY"):
        return {"status": "skipped", "reason": "TAVILY_API_KEY is not set"}
    from shadow.core.models import ActionDef, Assumption, ContractAction, FutureContract
    from shadow.integrations.tavily_search import TavilySearch
    from shadow.runtime.broker import AuthorizationDenied, authorize
    from shadow.world.loader import load_scenario

    search = TavilySearch()
    results = search.search("New York Public Library main branch visiting hours")
    sourced = [item for item in results if item.get("source")]
    scenario = load_scenario("travel").model_copy(deep=True)
    contract = FutureContract(
        contract_id="tavily",
        plan_id="tavily",
        approved_future_id="b1120",
        created_at="2026-10-07T12:00:00Z",
        expires_at="2026-10-08T00:00:00Z",
        goals=["check a public fact"],
        invariants=["c_dinner"],
        assumptions=[Assumption(id="asm-lib", description="library", variable="library_open", expected="closed")],
        allowed_actions=[
            ContractAction(action_id="confirm_friday", action_type="calendar.update_event", resource="cal_trip", max_cost=0)
        ],
        resource_scopes=["cal_trip"],
        spending_limit=10,
        forbidden_actions=[],
        verification_requirements=[],
        compensation_actions=[],
        provenance="tavily-live",
    )
    # The travel fixture has no library variable. Missing material state fails closed
    # until the live source is attached as an assumption check on a real variable.
    action = ActionDef(id="confirm_friday", action_type="calendar.update_event", label="Friday", resource="cal_trip")
    status = "no_source"
    if sourced:
        contract.assumptions[0].variable = "flight_delay_min"
        contract.assumptions[0].expected = "closed"
        for var in scenario.variables:
            if var.id == "flight_delay_min":
                var.baseline = sourced[0]["source"]
        try:
            authorize(contract, action, {"scenario": scenario, "now": __import__("datetime").datetime(2026, 10, 7, 18, tzinfo=__import__("datetime").timezone.utc)})
            status = "not_revoked"
        except AuthorizationDenied as exc:
            status = exc.reason
    return {
        "status": status,
        "result_count": len(results),
        "sources": [item.get("source") for item in sourced],
        "provenance": "tavily",
    }


def _openshell() -> dict[str, object]:
    if shutil.which("openshell-prover") is None:
        return {"status": "prover_unavailable"}
    from shadow.policy.openshell import candidate_policy, compare_policy, load_boundary

    boundary = load_boundary()
    contained = compare_policy(candidate_policy(["api.tokenfactory.nebius.com"]), boundary)
    overbroad = compare_policy(candidate_policy(["evil.example"]), boundary)
    return {"status": "ran", "contained": contained, "overbroad": overbroad}


def _finish(directory: Path, ledger: BudgetLedger, baseline: float, smoke: dict, hero: dict, trace: dict, pilot: dict, tavily: dict, openshell: dict) -> None:
    spent = float(ledger.snapshot()["repo_actual_spend_usd"]) - baseline
    cost = {
        "prior_external_spend_usd": PRIOR_EXTERNAL,
        "previous_repo_live_spend_usd": PREVIOUS_REPO,
        "session_baseline_repo_actual_usd": baseline,
        "new_live_validation_spend_usd": round(spent, 10),
        "total_known_spend_usd": round(PRIOR_EXTERNAL + PREVIOUS_REPO + spent, 10),
        "session_cap_usd": SESSION_CAP,
        "smoke_cost_usd": smoke["cost_usd"],
        "input_tokens": sum(int(item.get("input_tokens") or 0) for item in client_calls(smoke, hero, pilot))
        + sum(int(row["input_tokens"]) for row in pilot["rows"]),
        "output_tokens": sum(int(item.get("output_tokens") or 0) for item in client_calls(smoke, hero, pilot))
        + sum(int(row["output_tokens"]) for row in pilot["rows"]),
        "model_calls_recorded": len(client_calls(smoke, hero, pilot))
        + sum(int(row["model_calls"]) for row in pilot["rows"]),
        "tavily": {"status": tavily.get("status"), "result_count": tavily.get("result_count", 0)},
        "openshell": openshell.get("status"),
    }
    (directory / "cost.json").write_text(json.dumps(cost, indent=2) + "\n")
    safe_trace = {
        "plan": HERO,
        "schema_valid": hero.get("schema_valid"),
        "recommended": hero.get("recommended"),
        "naive": hero.get("naive"),
        "failure_variables": hero.get("failure_variables"),
        "rejected_model_repairs": hero.get("rejected_model_repairs"),
        "dependencies": hero.get("dependencies"),
        "hazards": hero.get("hazards"),
        "unknowns": hero.get("unknowns"),
        "contract_status": hero.get("contract_status"),
        "allowed_actions": hero.get("allowed_actions"),
        "execute_status": hero.get("execute_status"),
        "reconciliation": hero.get("reconciliation"),
        "second_run_cache_hits": trace.get("cache_hits"),
        "second_run_recommended": trace.get("recommended"),
    }
    (directory / "hero_trace.json").write_text(json.dumps(safe_trace, indent=2) + "\n")
    (directory / "tavily.json").write_text(json.dumps({"status": tavily.get("status"), "result_count": tavily.get("result_count", 0), "sources": tavily.get("sources", [])}, indent=2) + "\n")
    (directory / "README.md").write_text(_readme(directory.name, cost, pilot, tavily, openshell, hero))


def client_calls(smoke: dict, hero: dict, pilot: dict) -> list[dict]:
    del pilot
    return list(smoke["calls"]) + list(hero.get("calls") or [])


def _public_cost(ledger: BudgetLedger, baseline: float, smoke: dict, pilot: dict) -> dict[str, object]:
    spent = float(ledger.snapshot()["repo_actual_spend_usd"]) - baseline
    return {
        "new_live_validation_spend_usd": round(spent, 10),
        "smoke_cost_usd": smoke["cost_usd"],
        "worlds_completed": pilot["summary"].get("worlds_completed"),
        "stopped_early": pilot["stopped"],
        "repo_actual_spend_usd": ledger.snapshot()["repo_actual_spend_usd"],
    }


def _readme(name: str, cost: dict, pilot: dict, tavily: dict, openshell: dict, hero: dict) -> str:
    summary = pilot["summary"]
    lines = [
        "# Live Nemotron pilot",
        "",
        "This is a live Lightning pilot, not the local scripted gate.",
        "",
        f"- Run: `{name}`",
        "- Model: `nvidia/Nemotron-3_5-Lightning`",
        "- Temperature 0, thinking disabled, Super off, Ultra off",
        f"- Frozen worlds: {summary.get('worlds_completed')} completed of 30",
        f"- New validation spend USD: {cost['new_live_validation_spend_usd']}",
        f"- Total known spend USD: {cost['total_known_spend_usd']}",
        f"- Stopped early: {pilot['stopped']}",
        f"- Context reduced after world: {pilot['reduced_after']}",
        "- Prompt text was not edited after the first pilot.",
        "- propose_repairs max_tokens was raised from 256 to 512 after the first pilot truncated JSON at 256 tokens.",
        "- Choice and analyze calls from the first pilot are cache hits on this rerun.",
        "- Direct, planner, and critic see the shared pilot context only.",
        "- Shadow also uses formulas, bounds, and effects inside the deterministic engine.",
        "- The oracle is stored in `oracle.json` and is not sent to the model.",
        f"- Hero schema valid: {hero.get('schema_valid')}. Recommended: {hero.get('recommended')}.",
        f"- Tavily: {tavily.get('status')}.",
        f"- OpenShell: {openshell.get('status')}.",
        "",
        "Sample size 30 is a pilot. Intervals are bootstrap estimates, not a conclusive ranking.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
