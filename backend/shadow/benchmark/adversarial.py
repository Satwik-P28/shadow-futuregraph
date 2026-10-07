"""Hand-authored holdout. Same repair engine. No model calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shadow.core.models import Scenario
from shadow.repair.evaluate import evaluate_repairs, select_naive

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "shadowbench" / "adversarial_holdout" / "cases.json"


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES.read_text())


def scenario_for(case: dict[str, Any]) -> Scenario:
    kind = case["kind"]
    if kind == "unknown":
        return _unknown(case["id"])
    if kind == "contradiction":
        return _flag_conflict(case["id"])
    if kind == "impossible":
        return _impossible(case["id"])
    if kind == "sequence":
        return _sequence(case["id"])
    if kind == "person":
        return _person(case)
    return _slack(case)


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    scenario = scenario_for(case)
    proposals = [(bundle.id, bundle.label, bundle.action_ids, "catalog") for bundle in scenario.bundles]
    repairs = evaluate_repairs(scenario, proposals, seed=11)
    recommended = next((item.id for item in repairs if item.recommended), None)
    naive = select_naive(scenario)
    by_id = {item.id: item for item in repairs}
    naive_failures = [] if naive is None or naive not in by_id else by_id[naive].failures
    discovered = sorted({pert.variable for item in naive_failures for pert in item.perturbations})
    expected_cut = case.get("cut") or []
    if case.get("naive_fails") and expected_cut:
        recall_hit = len(set(discovered) & set(expected_cut))
        recall_total = len(expected_cut)
    else:
        recall_hit = 0
        recall_total = 0
    false_hazard = bool(naive_failures) and not case.get("naive_fails")
    best = case.get("best")
    repair_ok = recommended == best
    unknown_ok = True
    if case.get("unknown"):
        unknown_ok = recommended is None and all(item.modeled_success_rate is None for item in repairs)
    return {
        "id": case["id"],
        "recommended": recommended,
        "naive": naive,
        "task_ok": repair_ok,
        "repair_ok": repair_ok,
        "false_hazard": false_hazard,
        "recall_hit": recall_hit,
        "recall_total": recall_total,
        "unknown_ok": unknown_ok,
        "regret": 0.0 if repair_ok else 1.0,
        "no_search_ok": naive == best,
        "no_search_regret": 0.0 if naive == best else 1.0,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    recall_hit = sum(row["recall_hit"] for row in rows)
    recall_total = sum(row["recall_total"] for row in rows)
    return {
        "shadow_task": f"{sum(row['task_ok'] for row in rows)}/{count}",
        "shadow_no_search_task": f"{sum(row['no_search_ok'] for row in rows)}/{count}",
        "failure_recall": f"{recall_hit}/{recall_total}",
        "false_hazards": f"{sum(row['false_hazard'] for row in rows)}/{count}",
        "repair_success": f"{sum(row['repair_ok'] for row in rows)}/{count}",
        "unknown_handling": f"{sum(row['unknown_ok'] for row in rows)}/{count}",
        "mean_regret": round(sum(row["regret"] for row in rows) / count, 3) if count else None,
        "no_search_mean_regret": round(sum(row["no_search_regret"] for row in rows) / count, 3) if count else None,
        "rows": rows,
    }


def _slack(case: dict[str, Any]) -> Scenario:
    bundles = []
    actions = []
    for item in case["bundles"]:
        actions.append(
            {
                "id": item["id"],
                "action_type": "schedule.set",
                "label": item["id"],
                "resource": "trip",
                "cost": item["cost"],
                "effects": {"departure_min": item["dep"]},
            }
        )
        bundles.append({"id": item["id"], "label": item["id"], "action_ids": [item["id"]]})
    constraints = [_dinner()]
    variables = _travel_vars(case["baseline_dep"])
    if "budget" in case:
        variables.append(
            {
                "id": "trip_cost",
                "label": "Trip cost",
                "role": "derived",
                "vtype": "number",
                "epistemic_status": "COMPUTED",
                "formula": {"op": "var", "ref": "departure_cost"},
            }
        )
        for action, item in zip(actions, case["bundles"], strict=True):
            action["effects"]["departure_cost"] = item["cost"]
        variables.append(
            {
                "id": "departure_cost",
                "label": "Bundle cost",
                "role": "controllable",
                "vtype": "number",
                "baseline": 0,
                "epistemic_status": "VERIFIED",
            }
        )
        constraints.append(
            {
                "id": "c_budget",
                "label": "Cost cap",
                "kind": "resource",
                "hardness": "hard",
                "description": "Stay within the cap.",
                "expr": {
                    "op": "lte",
                    "args": [{"op": "var", "ref": "trip_cost"}, {"op": "const", "value": case["budget"]}],
                },
            }
        )
    return _scenario(case["id"], variables, constraints, actions, bundles)


def _person(case: dict[str, Any]) -> Scenario:
    variables = _travel_vars(case["baseline_dep"])
    variables.append(
        {
            "id": "dinner_fixed",
            "label": "Dinner with Sam",
            "role": "controllable",
            "vtype": "bool",
            "baseline": True,
            "epistemic_status": "VERIFIED",
        }
    )
    constraints = [
        _dinner(),
        {
            "id": "c_person",
            "label": "Sam's dinner stays",
            "kind": "boolean",
            "hardness": "hard",
            "description": "Another person cannot move.",
            "expr": {"op": "eq", "args": [{"op": "var", "ref": "dinner_fixed"}, {"op": "const", "value": True}]},
        },
    ]
    actions = [
        {
            "id": "fragile",
            "action_type": "schedule.set",
            "label": "fragile",
            "resource": "trip",
            "cost": 0,
            "effects": {"departure_min": 880},
        },
        {
            "id": "keep_dinner",
            "action_type": "schedule.set",
            "label": "keep_dinner",
            "resource": "trip",
            "cost": 40,
            "effects": {"departure_min": 680, "dinner_fixed": True},
        },
        {
            "id": "move_dinner",
            "action_type": "schedule.set",
            "label": "move_dinner",
            "resource": "dinner",
            "cost": 5,
            "effects": {"departure_min": 880, "dinner_fixed": False},
        },
    ]
    bundles = [{"id": item["id"], "label": item["id"], "action_ids": [item["id"]]} for item in actions]
    return _scenario(case["id"], variables, constraints, actions, bundles)


def _sequence(case_id: str) -> Scenario:
    variables = [
        {
            "id": "departure_min",
            "label": "Departure",
            "role": "controllable",
            "vtype": "number",
            "baseline": 880,
            "epistemic_status": "VERIFIED",
        },
        {
            "id": "ride_min",
            "label": "Ride",
            "role": "controllable",
            "vtype": "number",
            "baseline": 725,
            "epistemic_status": "VERIFIED",
        },
        {
            "id": "ride_expected",
            "label": "Ride expected",
            "role": "derived",
            "vtype": "number",
            "epistemic_status": "COMPUTED",
            "formula": {"op": "sub", "args": [{"op": "var", "ref": "departure_min"}, {"op": "const", "value": 155}]},
        },
    ]
    constraints = [
        {
            "id": "c_seq",
            "label": "Ride follows flight",
            "kind": "sequence",
            "hardness": "hard",
            "description": "The ride has to move with the flight.",
            "expr": {"op": "eq", "args": [{"op": "var", "ref": "ride_min"}, {"op": "var", "ref": "ride_expected"}]},
        }
    ]
    actions = [
        {
            "id": "flight_only",
            "action_type": "schedule.set",
            "label": "flight_only",
            "resource": "flight",
            "cost": 0,
            "effects": {"departure_min": 680},
        },
        {
            "id": "with_ride",
            "action_type": "schedule.set",
            "label": "with_ride",
            "resource": "trip",
            "cost": 10,
            "effects": {"departure_min": 680, "ride_min": 525},
        },
    ]
    bundles = [{"id": item["id"], "label": item["id"], "action_ids": [item["id"]]} for item in actions]
    return _scenario(case_id, variables, constraints, actions, bundles)


def _unknown(case_id: str) -> Scenario:
    return Scenario.model_validate(
        {
            "id": case_id,
            "title": case_id,
            "domain": "scheduling",
            "plan_prompt": "Book only if the venue is known.",
            "variables": [
                {
                    "id": "venue_open",
                    "label": "Venue",
                    "role": "exogenous",
                    "vtype": "bool",
                    "baseline": None,
                    "distribution": "unknown",
                    "epistemic_status": "UNKNOWN",
                }
            ],
            "constraints": [
                {
                    "id": "c_venue",
                    "label": "Venue known",
                    "kind": "boolean",
                    "hardness": "hard",
                    "description": "Do not guess the venue.",
                    "expr": {"op": "eq", "args": [{"op": "var", "ref": "venue_open"}, {"op": "const", "value": True}]},
                }
            ],
            "actions": [
                {
                    "id": "book",
                    "action_type": "schedule.book",
                    "label": "book",
                    "resource": "workshop",
                    "cost": 10,
                    "effects": {},
                }
            ],
            "bundles": [{"id": "book", "label": "book", "action_ids": ["book"]}],
            "facts": [],
        }
    )


def _flag_conflict(case_id: str) -> Scenario:
    return Scenario.model_validate(
        {
            "id": case_id,
            "title": case_id,
            "domain": "scheduling",
            "plan_prompt": "Two sources disagree.",
            "variables": [
                {
                    "id": "flag",
                    "label": "Status",
                    "role": "controllable",
                    "vtype": "number",
                    "baseline": 1,
                    "epistemic_status": "VERIFIED",
                }
            ],
            "constraints": [
                {
                    "id": "c_yes",
                    "label": "Source A says yes",
                    "kind": "equality",
                    "hardness": "hard",
                    "description": "One source requires yes.",
                    "expr": {"op": "eq", "args": [{"op": "var", "ref": "flag"}, {"op": "const", "value": 1}]},
                },
                {
                    "id": "c_no",
                    "label": "Source B says no",
                    "kind": "equality",
                    "hardness": "hard",
                    "description": "The other source requires no.",
                    "expr": {"op": "eq", "args": [{"op": "var", "ref": "flag"}, {"op": "const", "value": 0}]},
                },
            ],
            "actions": [
                {
                    "id": "keep",
                    "action_type": "schedule.set",
                    "label": "keep",
                    "resource": "status",
                    "cost": 0,
                    "effects": {"flag": 1},
                }
            ],
            "bundles": [{"id": "keep", "label": "keep", "action_ids": ["keep"]}],
            "facts": [],
        }
    )


def _impossible(case_id: str) -> Scenario:
    variables = [
        {
            "id": "departure_min",
            "label": "Departure",
            "role": "controllable",
            "vtype": "number",
            "baseline": 400,
            "epistemic_status": "VERIFIED",
        },
        {
            "id": "arrival_min",
            "label": "Arrival",
            "role": "derived",
            "vtype": "number",
            "epistemic_status": "COMPUTED",
            "formula": {"op": "add", "args": [{"op": "var", "ref": "departure_min"}, {"op": "const", "value": 100}]},
        },
    ]
    constraints = [
        {
            "id": "c_early",
            "label": "Arrive by 08:20",
            "kind": "temporal",
            "hardness": "hard",
            "description": "Too early.",
            "expr": {"op": "lte", "args": [{"op": "var", "ref": "arrival_min"}, {"op": "const", "value": 500}]},
        },
        {
            "id": "c_late",
            "label": "Do not arrive before 20:00",
            "kind": "temporal",
            "hardness": "hard",
            "description": "Too late.",
            "expr": {"op": "gte", "args": [{"op": "var", "ref": "arrival_min"}, {"op": "const", "value": 1200}]},
        },
    ]
    actions = [
        {
            "id": "go",
            "action_type": "schedule.set",
            "label": "go",
            "resource": "trip",
            "cost": 0,
            "effects": {"departure_min": 400},
        }
    ]
    return _scenario(case_id, variables, constraints, actions, [{"id": "go", "label": "go", "action_ids": ["go"]}])


def _travel_vars(baseline_dep: int) -> list[dict[str, Any]]:
    return [
        {
            "id": "departure_min",
            "label": "Departure",
            "role": "controllable",
            "vtype": "number",
            "baseline": baseline_dep,
            "epistemic_status": "VERIFIED",
            "show_in_diff": True,
        },
        {
            "id": "flight_delay_min",
            "label": "Delay",
            "role": "exogenous",
            "vtype": "number",
            "baseline": 0,
            "lower": 0,
            "upper": 180,
            "scale": 180,
            "distribution": "uniform",
            "epistemic_status": "ESTIMATED",
        },
        {
            "id": "traffic_extra_min",
            "label": "Traffic",
            "role": "exogenous",
            "vtype": "number",
            "baseline": 0,
            "lower": 0,
            "upper": 150,
            "scale": 150,
            "distribution": "uniform",
            "epistemic_status": "ESTIMATED",
        },
        {
            "id": "dinner_deadline_min",
            "label": "Dinner",
            "role": "fixed",
            "vtype": "number",
            "baseline": 1140,
            "epistemic_status": "VERIFIED",
        },
        {
            "id": "arrival_min",
            "label": "Arrival",
            "role": "derived",
            "vtype": "number",
            "epistemic_status": "COMPUTED",
            "formula": {
                "op": "add",
                "args": [
                    {"op": "var", "ref": "departure_min"},
                    {"op": "const", "value": 145},
                    {"op": "var", "ref": "flight_delay_min"},
                    {"op": "var", "ref": "traffic_extra_min"},
                ],
            },
        },
    ]


def _dinner() -> dict[str, Any]:
    return {
        "id": "c_dinner",
        "label": "Arrive by dinner",
        "kind": "temporal",
        "hardness": "hard",
        "description": "Reach dinner.",
        "expr": {
            "op": "lte",
            "args": [
                {"op": "var", "ref": "arrival_min"},
                {"op": "var", "ref": "dinner_deadline_min"},
            ],
        },
    }


def _scenario(
    case_id: str,
    variables: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    bundles: list[dict[str, Any]],
) -> Scenario:
    return Scenario.model_validate(
        {
            "id": case_id,
            "title": case_id,
            "domain": "scheduling",
            "plan_prompt": case_id,
            "variables": variables,
            "constraints": constraints,
            "actions": actions,
            "bundles": bundles,
            "facts": [],
        }
    )
