"""Live Lightning pilot. Worlds are frozen before the first paid call."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from shadow.benchmark.live_worlds import assess, generate_world, optimal_bundle, pilot_context
from shadow.benchmark.metrics import summarize
from shadow.core.models import ChoiceSpec, PlanSpec, RepairProposal
from shadow.future_graph.build import build_graph
from shadow.llm.budget import BudgetError
from shadow.llm.client import PURPOSE_TOKENS, SchemaError, prompt_hash
from shadow.repair.evaluate import evaluate_repairs, select_naive

SYSTEMS = ("direct_nemotron", "planner", "planner_critic", "shadow", "shadow_no_failure_search")


def run_pilot(
    client: Any,
    ledger: Any,
    directory: Path,
    *,
    session_baseline: float,
    session_cap: float = 0.03,
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    frozen = [generate_world(index) for index in range(30)]
    _write_frozen(directory, frozen)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    reduced_after: int | None = None
    stopped = False
    stop_reason = ""
    spent_at_start = _spent(ledger, session_baseline)
    for index, (scenario, oracle) in enumerate(frozen):
        if index == 5:
            incremental = _spent(ledger, session_baseline) - spent_at_start
            projected = incremental / 5 * 30
            if projected > session_cap:
                reduced_after = 5
        context = pilot_context(scenario)
        if reduced_after is not None:
            context = _shrink(context)
        try:
            world_rows, world_errors = _world(client, scenario, oracle, context, index)
        except BudgetError:
            stopped = True
            stop_reason = "session cap would be exceeded"
            break
        rows.extend(world_rows)
        errors.extend(world_errors)
        _append_jsonl(directory / "raw.jsonl", world_rows)
        print(f"world {index} spent {_spent(ledger, session_baseline):.6f}", flush=True)
    summary = summarize(rows) if rows else {"systems": {}, "n": 0}
    summary["label"] = "LIVE PILOT"
    summary["worlds_completed"] = len({row["world_id"] for row in rows})
    summary["stopped_early"] = stopped
    summary["stop_reason"] = stop_reason
    summary["context_reduced_after_world"] = reduced_after
    payload = {
        "rows": rows,
        "errors": errors,
        "summary": summary,
        "stopped": stopped,
        "reduced_after": reduced_after,
    }
    _write_tables(directory, payload, session_baseline, session_cap)
    return payload


def _world(
    client: Any,
    scenario: Any,
    oracle: dict[str, Any],
    context: dict[str, Any],
    index: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundle_ids = {bundle.id: bundle.action_ids for bundle in scenario.bundles}
    naive = select_naive(scenario)
    optimal = oracle["optimal"]
    if optimal != optimal_bundle(scenario):
        raise RuntimeError("frozen oracle disagrees with the scorer")
    direct = _choice_call(client, "direct_choice", context, bundle_ids)
    planner = _choice_call(client, "plan_choice", context, bundle_ids)
    critic = _critic(client, context, bundle_ids, planner)
    shadow = _shadow(client, scenario, context, oracle, index)
    nominal = {
        "choice": naive,
        "format_failure": shadow["format_failure"],
        "hazards": [],
        "unknowns": [],
        "rejected": shadow["rejected"],
        "repairs": shadow["repairs"],
        "graph_recall": None,
        "cut_precision": None,
        "cut_recall": None,
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": 0.0,
        "spec_dependencies": shadow["spec_dependencies"],
    }
    choices = {
        "direct_nemotron": direct,
        "planner": planner,
        "planner_critic": critic,
        "shadow": shadow,
        "shadow_no_failure_search": nominal,
    }
    rows = []
    errors = []
    naive_safe = bool(naive and assess(scenario, bundle_ids[naive])["safe"])
    fragile = not naive_safe
    for system in SYSTEMS:
        item = choices[system]
        choice = item["choice"]
        executed_fails = bool(choice and not assess(scenario, bundle_ids[choice])["safe"])
        task_complete = (choice is None and optimal is None) or bool(choice and assess(scenario, bundle_ids[choice])["safe"])
        repair_success = choice == optimal
        if not repair_success and task_complete and choice and optimal:
            regret = abs(assess(scenario, bundle_ids[choice])["cost"] - assess(scenario, bundle_ids[optimal])["cost"])
            base = assess(scenario, bundle_ids[optimal])["cost"] or 1.0
            regret = regret / base
        elif repair_success:
            regret = 0.0
        else:
            regret = 1.0
        false_hazard = bool(naive_safe and optimal == naive and choice != naive)
        if naive is None:
            recall = 1.0 if choice is None or not executed_fails else 0.0
        elif not naive_safe:
            recall = 1.0 if choice != naive else 0.0
        else:
            recall = 1.0
        row = {
            "world_id": scenario.id,
            "structure": oracle["structure"],
            "family": oracle["domain"],
            "seed": 5000 + index,
            "system": system,
            "choice": choice,
            "naive": naive,
            "oracle_optimal": optimal,
            "oracle_fragile": fragile,
            "executed_fails": executed_fails,
            "flagged_failure": bool(fragile and choice != naive and not executed_fails),
            "task_complete": task_complete,
            "failure_recall_hit": recall,
            "false_hazard": false_hazard,
            "repair_success": repair_success,
            "regret": regret,
            "cut_precision": item.get("cut_precision") if system == "shadow" and fragile else None,
            "cut_recall": item.get("cut_recall") if system == "shadow" and fragile else None,
            "unknown_calibrated": (not oracle.get("unknown")) or choice is None,
            "edge_recall": item.get("graph_recall") if system == "shadow" else 0.0,
            "converged": task_complete,
            "model_calls": item["model_calls"],
            "input_tokens": item["input_tokens"],
            "output_tokens": item["output_tokens"],
            "cost_usd": item["cost_usd"],
            "latency_ms": item["latency_ms"],
            "format_failure": item["format_failure"],
            "invalid_bundle": item.get("invalid_bundle", False),
        }
        rows.append(row)
        errors.extend(_errors(scenario, oracle, row, item))
    return rows, errors


def _choice_call(client: Any, purpose: str, context: dict[str, Any], bundle_ids: dict[str, list[str]]) -> dict[str, Any]:
    started = time.perf_counter()
    before = len(client.calls)
    invalid = False
    failure = False
    choice = None
    hazards: list[str] = []
    unknowns: list[str] = []
    try:
        parsed = client.complete_json(purpose, context, ChoiceSpec)
        hazards = list(parsed.hazards)
        unknowns = list(parsed.unknowns)
        if parsed.bundle_id in bundle_ids:
            choice = parsed.bundle_id
        elif parsed.bundle_id:
            invalid = True
    except (SchemaError, ValidationError):
        failure = True
    spent = _usage(client, before)
    spent.update(
        {
            "choice": choice,
            "format_failure": failure,
            "invalid_bundle": invalid,
            "hazards": hazards,
            "unknowns": unknowns,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "rejected": [],
            "spec_dependencies": [],
        }
    )
    return spent


def _critic(client: Any, context: dict[str, Any], bundle_ids: dict[str, list[str]], proposal: dict[str, Any]) -> dict[str, Any]:
    if proposal["format_failure"]:
        reviewed = dict(proposal)
        reviewed["model_calls"] = proposal["model_calls"]
        return reviewed
    review_context = dict(context)
    review_context["proposal"] = {"bundle_id": proposal["choice"], "hazards": proposal["hazards"], "unknowns": proposal["unknowns"]}
    reviewed = _choice_call(client, "critique_choice", review_context, bundle_ids)
    reviewed["model_calls"] += proposal["model_calls"]
    reviewed["input_tokens"] += proposal["input_tokens"]
    reviewed["output_tokens"] += proposal["output_tokens"]
    reviewed["cost_usd"] += proposal["cost_usd"]
    reviewed["latency_ms"] += proposal["latency_ms"]
    reviewed["format_failure"] = proposal["format_failure"] or reviewed["format_failure"]
    return reviewed


def _shadow(
    client: Any,
    scenario: Any,
    context: dict[str, Any],
    oracle: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    before = len(client.calls)
    failure = False
    spec = None
    try:
        spec = client.complete_json("analyze_plan", context, PlanSpec)
    except (SchemaError, ValidationError):
        failure = True
    proposals: list[Any] = []
    if spec is not None:
        try:
            proposals = client.complete_json("propose_repairs", context, RepairProposal).repairs
        except (SchemaError, ValidationError):
            failure = True
    catalog = [(bundle.id, bundle.label, bundle.action_ids, "catalog") for bundle in scenario.bundles]
    model_rows = []
    for item in proposals[:5]:
        if all(action_id in {action.id for action in scenario.actions} for action_id in item.action_ids):
            model_rows.append((item.id, item.label, item.action_ids, "model"))
    repairs = evaluate_repairs(scenario, catalog + model_rows, seed=5000 + index)
    recommended = next((item for item in repairs if item.recommended), None)
    naive = select_naive(scenario)
    by_id = {item.id: item for item in repairs}
    naive_failures = [] if naive is None or naive not in by_id else by_id[naive].failures
    discovered = {pert.variable for failure in naive_failures for pert in failure.perturbations}
    material = set(oracle.get("minimal_cut") or [])
    naive_safe = False
    if naive is not None:
        naive_actions = next(bundle.action_ids for bundle in scenario.bundles if bundle.id == naive)
        naive_safe = assess(scenario, naive_actions)["safe"]
    if naive_safe or not material:
        cut_precision = None
        cut_recall = None
    else:
        cut_precision = (len(discovered & material) / len(discovered)) if discovered else 0.0
        cut_recall = len(discovered & material) / len(material)
    graph = build_graph(scenario, repairs, naive_id=naive, recommended_id=None if recommended is None else recommended.id)
    present = {node.id.removeprefix("var:") for node in graph.nodes}
    edges = set(oracle.get("material_edges") or [])
    graph_recall = (sum(1 for item in edges if item in present) / len(edges)) if edges else None
    spent = _usage(client, before)
    rejected = [
        {"id": item.id, "status": item.status, "source": item.source}
        for item in repairs
        if item.source == "model" and (item.hard_violations or item.unresolved_hard or item.failures)
    ]
    spent.update(
        {
            "choice": None if recommended is None else recommended.id,
            "format_failure": failure,
            "invalid_bundle": False,
            "hazards": [] if spec is None else [item.description for item in spec.hazards],
            "unknowns": [] if spec is None else list(spec.unknowns),
            "latency_ms": (time.perf_counter() - started) * 1000,
            "rejected": rejected,
            "repairs": repairs,
            "discovered_cut": sorted(discovered),
            "cut_precision": cut_precision,
            "cut_recall": cut_recall,
            "graph_recall": graph_recall,
            "spec_dependencies": [] if spec is None else [item.model_dump(mode="json") for item in spec.dependencies],
        }
    )
    return spent


def _errors(scenario: Any, oracle: dict[str, Any], row: dict[str, Any], item: dict[str, Any]) -> list[dict[str, Any]]:
    categories = []
    if row["format_failure"]:
        categories.append("format failure")
    if row["invalid_bundle"]:
        categories.append("bad candidate generation")
    if row["false_hazard"]:
        categories.append("unnecessary veto")
    if row["executed_fails"] and row["choice"] == row["naive"]:
        categories.append("nominal-only reasoning")
    elif row["executed_fails"]:
        categories.append("wrong repair")
    if oracle.get("unknown") and row["choice"] is not None:
        categories.append("ignored unknown")
    if oracle["structure"] == "stale_fact" and row["executed_fails"]:
        categories.append("stale-fact failure")
    if oracle["structure"] == "repair_tradeoff" and row["choice"] == "opt_patch":
        categories.append("repair introduces new violation")
    if not categories:
        return []
    component = ""
    if row["system"] == "shadow":
        component = _component(scenario, oracle, row, item)
    return [
        {
            "world_id": row["world_id"],
            "structure": oracle["structure"],
            "system": row["system"],
            "category": category,
            "component": component,
            "choice": row["choice"],
            "optimal": oracle["optimal"],
        }
        for category in categories
    ]


def _component(scenario: Any, oracle: dict[str, Any], row: dict[str, Any], item: dict[str, Any]) -> str:
    if row["format_failure"]:
        return "NEMOTRON"
    repairs = item.get("repairs") or []
    by_id = {repair.id: repair for repair in repairs}
    optimal = oracle["optimal"]
    if optimal and optimal in by_id:
        view = assess(scenario, by_id[optimal].action_ids)
        if view["safe"] and by_id[optimal].failures:
            return "SEARCH"
        if view["safe"] and (by_id[optimal].hard_violations or by_id[optimal].unresolved_hard):
            return "REPAIR"
    naive = row["naive"]
    if naive and naive in by_id:
        view = assess(scenario, by_id[naive].action_ids)
        if not view["safe"] and not by_id[naive].failures and by_id[naive].hard_violations == 0 and by_id[naive].unresolved_hard == 0:
            return "SEARCH"
    if row["choice"] and row["choice"] in by_id and by_id[row["choice"]].source == "model" and row["executed_fails"]:
        return "REPAIR"
    if oracle.get("unknown") and row["choice"] is not None:
        return "NEMOTRON"
    if oracle.get("material_edges") and item.get("graph_recall") is not None and item["graph_recall"] < 1:
        return "GRAPH"
    return "REPAIR"


def _usage(client: Any, before: int) -> dict[str, Any]:
    fresh = client.calls[before:]
    return {
        "model_calls": len(fresh),
        "input_tokens": sum(int(item.get("input_tokens") or 0) for item in fresh),
        "output_tokens": sum(int(item.get("output_tokens") or 0) for item in fresh),
        "cost_usd": sum(float(item.get("actual_cost_usd") or item.get("cost_usd") or 0) for item in fresh),
    }


def _shrink(context: dict[str, Any]) -> dict[str, Any]:
    shrunk = dict(context)
    shrunk["facts"] = context["facts"][:2]
    shrunk["constraints"] = [
        {**item, "description": item["description"][:80]} for item in context["constraints"]
    ]
    return shrunk


def _spent(ledger: Any, baseline: float) -> float:
    return float(ledger.snapshot()["repo_actual_spend_usd"]) - baseline


def _write_frozen(directory: Path, frozen: list[tuple[Any, dict[str, Any]]]) -> None:
    worlds = [scenario.model_dump(mode="json") for scenario, _ in frozen]
    oracles = [oracle for _, oracle in frozen]
    (directory / "worlds.json").write_text(json.dumps(worlds, indent=2) + "\n")
    (directory / "oracle.json").write_text(json.dumps(oracles, indent=2) + "\n")


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("a") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_tables(directory: Path, payload: dict[str, Any], baseline: float, cap: float) -> None:
    rows = payload["rows"]
    (directory / "summary.json").write_text(json.dumps(payload["summary"], indent=2) + "\n")
    (directory / "errors.csv").write_text(_csv(payload["errors"]))
    if rows:
        (directory / "metrics.csv").write_text(_csv(rows))
    config = {
        "label": "LIVE PILOT",
        "model": "nvidia/Nemotron-3_5-Lightning",
        "temperature": 0,
        "thinking": False,
        "n_frozen": 30,
        "systems": list(SYSTEMS),
        "seeds": "5000:5030",
        "session_cap_usd": cap,
        "session_baseline_usd": baseline,
        "prompts": {name: prompt_hash(filename) for name, (filename, _) in PURPOSE_TOKENS.items()},
        "max_tokens": {name: tokens for name, (_, tokens) in PURPOSE_TOKENS.items()},
        "context_reduced_after_world": payload["reduced_after"],
        "stopped_early": payload["stopped"],
        "evidence_note": (
            "Every system receives the same pilot context: plan, bundle ids, labels, costs, "
            "constraint descriptions, unknowns, and facts. Shadow's deterministic engine also "
            "reads formulas, bounds, and action effects. Those fields are required to calculate "
            "the future and are not sent to direct, planner, or critic. Oracle fields are not "
            "sent to any system."
        ),
    }
    (directory / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    _plots(payload["summary"], directory / "plots")


def _csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    fieldnames = list(rows[0].keys())
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        flat = {key: row.get(key) for key in fieldnames}
        writer.writerow(flat)
    return buffer.getvalue()


def _plots(summary: dict[str, Any], directory: Path) -> None:
    if not summary.get("systems"):
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    directory.mkdir(parents=True, exist_ok=True)
    systems = list(summary["systems"])
    specs = [
        ("task_completion.png", "Task completion", ["TaskCompletionRate", "rate"]),
        ("undetected_failure.png", "Undetected failure", ["UndetectedFailureRate", "rate"]),
        ("repair_success.png", "Repair success", ["RepairSuccessRate", "rate"]),
        ("cost.png", "Cost USD", ["CostUSD"]),
    ]
    for filename, title, path in specs:
        values = []
        for system in systems:
            cursor = summary["systems"][system]
            for key in path:
                cursor = cursor[key]
            values.append(float(cursor))
        figure, axis = plt.subplots(figsize=(7.2, 4.2))
        axis.bar(systems, values, color="#7f8c99")
        axis.set_title(title)
        axis.tick_params(axis="x", rotation=20)
        if "Cost" not in title:
            axis.set_ylim(0, 1.05)
        figure.tight_layout()
        figure.savefig(directory / filename, dpi=140)
        plt.close(figure)

