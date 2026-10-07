"""PLAN → graph → failures → repairs → diff → approve → execute → reconcile."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from shadow.contracts.solver import linear_satisfiability
from shadow.core.format import format_value
from shadow.core.models import (
    Assumption,
    ContractAction,
    CoverageReport,
    DiffEntry,
    FutureContract,
    FutureDiff,
    PlanSpec,
    RepairProposal,
    Scenario,
)
from shadow.failures.search import describe_failure
from shadow.future_graph.build import build_graph
from shadow.integrations.sandbox import SandboxProviders
from shadow.llm.client import FakeNemotronClient
from shadow.repair.evaluate import binding_for, evaluate_repairs, select_naive
from shadow.retrieval.engine import compact_context, retrieve
from shadow.runtime.broker import AuthorizationDenied, authorize
from shadow.runtime.events import EventLog
from shadow.runtime.execute import execute_bundle
from shadow.simulation.engine import bind, evaluate_constraints, hard_status
from shadow.world.loader import action_map, effects_for, load_scenario


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PlanService:
    def __init__(self, events: EventLog, client: Any | None = None) -> None:
        self.events = events
        self.client = client or FakeNemotronClient()
        self.plans: dict[str, dict[str, Any]] = {}

    def create(self, text: str, scenario_id: str = "travel", seed: int = 7) -> dict[str, Any]:
        plan_id = uuid.uuid4().hex[:12]
        record = {
            "id": plan_id,
            "text": text,
            "scenario_id": scenario_id,
            "seed": seed,
            "status": "CREATED",
            "stages": [],
            "contract": None,
            "providers": SandboxProviders(),
            "scenario": load_scenario(scenario_id),
        }
        self.plans[plan_id] = record
        self.events.append(plan_id, "PLAN_CREATED", {"scenario_id": scenario_id}, "user")
        return {"id": plan_id, "status": "CREATED"}

    def analyze(self, plan_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        scenario: Scenario = record["scenario"]
        self._stage(record, "RETRIEVING_CONTEXT")
        found = retrieve(scenario, record["text"])
        context = compact_context(scenario, record["text"])
        self.events.append(plan_id, "FACT_RETRIEVED", {"counts": {key: len(value) for key, value in found.items()}}, "retrieval")
        spec = self.client.complete_json("analyze_plan", context, PlanSpec)
        self._stage(record, "BUILDING_GRAPH")
        catalog = [
            (bundle.id, bundle.label, bundle.action_ids, "catalog") for bundle in scenario.bundles
        ]
        proposal = self.client.complete_json("propose_repairs", context, RepairProposal)
        model_rows = [(item.id, item.label, item.action_ids, "model") for item in proposal.repairs[:5]]
        self._stage(record, "SEARCHING_FAILURES")
        self._stage(record, "TESTING_REPAIRS")
        repairs = evaluate_repairs(scenario, catalog + model_rows, seed=record["seed"])
        for repair in repairs:
            self.events.append(
                plan_id,
                "REPAIR_VALIDATED",
                {"id": repair.id, "status": repair.status, "radius": repair.failure_radius},
                "evaluator",
            )
        naive_id = select_naive(scenario)
        recommended = next((item for item in repairs if item.recommended), None)
        graph = build_graph(scenario, repairs, naive_id=naive_id, recommended_id=None if recommended is None else recommended.id)
        self.events.append(
            plan_id,
            "GRAPH_EDGE_VERIFIED",
            {"nodes": len(graph.nodes), "edges": len(graph.edges)},
            "graph",
        )
        diff = None
        if naive_id and recommended:
            diff = _diff(scenario, naive_id, recommended.id, repairs)
        coverage = _coverage(scenario)
        solver = linear_satisfiability(scenario)
        status = "READY" if recommended else "NO_FEASIBLE_FUTURE"
        record.update(
            {
                "status": status,
                "spec": spec,
                "repairs": repairs,
                "naive_id": naive_id,
                "recommended_id": None if recommended is None else recommended.id,
                "graph": graph,
                "diff": diff,
                "coverage": coverage,
                "retrieval": found,
                "solver": solver,
                "model_calls": getattr(self.client, "calls", 0) if isinstance(self.client.calls, int) else len(self.client.calls),
            }
        )
        self._stage(record, "READY")
        return self.view(plan_id)

    def approve(self, plan_id: str, repair_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        repair = next(item for item in record["repairs"] if item.id == repair_id)
        if repair.hard_violations or repair.unresolved_hard:
            raise ValueError("repair is not feasible")
        scenario: Scenario = record["scenario"]
        spec: PlanSpec = record["spec"]
        contract = _contract(plan_id, scenario, repair, spec)
        record["contract"] = contract
        record["status"] = "APPROVED"
        self.events.append(plan_id, "FUTURE_APPROVED", {"repair_id": repair_id}, "user")
        self.events.append(plan_id, "CONTRACT_CREATED", {"contract_id": contract.contract_id}, "contract")
        return contract.model_dump(mode="json")

    def execute(self, plan_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        contract: FutureContract | None = record.get("contract")
        if contract is None:
            raise ValueError("approve a future first")
        if contract.status in {"STALE", "HALTED"}:
            self.events.append(plan_id, "EXECUTION_HALTED", {"reason": "contract is not active"}, "runtime")
            return {"status": "halted", "reason": "Future no longer valid"}
        result = execute_bundle(
            scenario=record["scenario"],
            contract=contract,
            providers=record["providers"],
            events=self.events,
            plan_id=plan_id,
        )
        if result["status"] == "verified":
            contract.status = "COMPLETED"
            record["status"] = "RECONCILED"
            record["reconciliation"] = _reconcile(record)
        return result

    def attempt(self, plan_id: str, action_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        action = action_map(record["scenario"])[action_id]
        contract: FutureContract | None = record.get("contract")
        if contract is None:
            self.events.append(plan_id, "ACTION_BLOCKED", {"action_id": action_id, "reason": "no contract"}, "broker")
            return {"authorized": False, "message": "Blocked: action is outside the approved future."}
        try:
            authorize(contract, action, record["providers"].state)
        except AuthorizationDenied as exc:
            self.events.append(plan_id, "ACTION_BLOCKED", {"action_id": action_id, "reason": exc.reason}, "broker")
            return {"authorized": False, "message": "Blocked: action is outside the approved future."}
        return {"authorized": True, "message": "authorized"}

    def inject(self, plan_id: str, event_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        scenario: Scenario = record["scenario"]
        event = next(item for item in scenario.events if item.id == event_id)
        updated = scenario.model_copy(deep=True)
        for var in updated.variables:
            if var.id in event.set_baseline:
                var.baseline = event.set_baseline[var.id]
            if var.id in event.set_distribution:
                var.distribution = event.set_distribution[var.id]  # type: ignore[assignment]
                if var.distribution == "point" and isinstance(var.baseline, (int, float)):
                    var.lower = float(var.baseline)
                    var.upper = float(var.baseline)
        record["scenario"] = updated
        contract: FutureContract | None = record.get("contract")
        invalidated = []
        if contract:
            for assumption in contract.assumptions:
                if assumption.variable in event.set_baseline and event.set_baseline[assumption.variable] != assumption.expected:
                    assumption.status = "invalidated"
                    invalidated.append(assumption.variable)
                    self.events.append(
                        plan_id,
                        "ASSUMPTION_INVALIDATED",
                        {"assumption": assumption.variable, "event": event_id},
                        "inject",
                    )
        repairs = evaluate_repairs(
            updated,
            [(bundle.id, bundle.label, bundle.action_ids, "catalog") for bundle in updated.bundles],
            seed=record["seed"],
        )
        approved_id = None if contract is None else contract.approved_future_id
        approved = next((item for item in repairs if item.id == approved_id), None)
        holds = bool(approved and approved.feasible)
        if contract and not holds:
            contract.status = "STALE"
            record["status"] = "STALE"
            self.events.append(plan_id, "EXECUTION_HALTED", {"reason": "contract stale", "event": event_id}, "contract")
        elif contract and invalidated:
            contract.status = "REAFFIRMED"
            record["status"] = "REAFFIRMED"
        recommended = next((item for item in repairs if item.recommended), None)
        record["repairs"] = repairs
        record["naive_id"] = select_naive(updated)
        record["recommended_id"] = None if recommended is None else recommended.id
        record["graph"] = build_graph(
            updated,
            repairs,
            naive_id=record["naive_id"],
            recommended_id=record["recommended_id"],
        )
        if record["naive_id"] and record["recommended_id"]:
            record["diff"] = _diff(updated, record["naive_id"], record["recommended_id"], repairs)
        return {
            "event": event.model_dump(mode="json"),
            "invalidated": invalidated,
            "approved_future_holds": holds,
            "contract_status": None if contract is None else contract.status,
            "authority": "revoked" if contract and contract.status == "STALE" else "active",
            "recommended_repair_id": record["recommended_id"],
            "message": _inject_message(holds, invalidated),
        }

    def relax(self, plan_id: str, constraint_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        scenario: Scenario = record["scenario"].model_copy(deep=True)
        for constraint in scenario.constraints:
            if constraint.id == constraint_id and constraint.relaxable:
                constraint.hardness = "soft"
        record["scenario"] = scenario
        return self.analyze(plan_id)

    def view(self, plan_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        recommended = next((item for item in record.get("repairs", []) if item.recommended), None)
        naive = next((item for item in record.get("repairs", []) if item.id == record.get("naive_id")), None)
        return {
            "id": plan_id,
            "text": record["text"],
            "scenario_id": record["scenario_id"],
            "status": record["status"],
            "stages": record["stages"],
            "provider_mode": "SANDBOX",
            "solver": record.get("solver"),
            "coverage": None if "coverage" not in record else record["coverage"].model_dump(mode="json"),
            "graph": None if "graph" not in record else record["graph"].model_dump(mode="json"),
            "naive_repair_id": record.get("naive_id"),
            "recommended_repair_id": record.get("recommended_id"),
            "repairs": [item.model_dump(mode="json") for item in record.get("repairs", [])],
            "diff": None if record.get("diff") is None else record["diff"].model_dump(mode="json"),
            "failures": [] if naive is None else [item.model_dump(mode="json") for item in naive.failures],
            "unknowns": [] if "coverage" not in record else record["coverage"].unknown_ids,
            "contract": None if record.get("contract") is None else record["contract"].model_dump(mode="json"),
            "reconciliation": record.get("reconciliation"),
            "observability": {
                "model_calls": record.get("model_calls", 0),
                "worlds_simulated": sum(item.worlds_simulated for item in record.get("repairs", [])),
                "repairs_tested": len(record.get("repairs", [])),
                "selected_repair": record.get("recommended_id"),
                "graph_nodes": 0 if "graph" not in record else len(record["graph"].nodes),
                "graph_edges": 0 if "graph" not in record else len(record["graph"].edges),
            },
            "recommended_label": None if recommended is None else recommended.label,
            "no_feasible_message": None
            if record["status"] != "NO_FEASIBLE_FUTURE"
            else "No feasible future found under the current hard constraints.",
        }

    def _stage(self, record: dict[str, Any], name: str) -> None:
        record["stages"].append({"name": name, "at": _now()})


def _diff(scenario: Scenario, before_id: str, after_id: str, repairs: list[Any]) -> FutureDiff:
    before_bundle = next(item for item in scenario.bundles if item.id == before_id)
    after_bundle = next(item for item in scenario.bundles if item.id == after_id)
    before = binding_for(scenario, before_bundle.action_ids)
    after = binding_for(scenario, after_bundle.action_ids)
    entries = []
    for var in scenario.variables:
        if not var.show_in_diff:
            continue
        left = format_value(var.unit, before.get(var.id))
        right = format_value(var.unit, after.get(var.id))
        entries.append(DiffEntry(id=var.id, label=var.label, before=left, after=right, changed=left != right))
    before_metrics = next(item for item in repairs if item.id == before_id)
    after_metrics = next(item for item in repairs if item.id == after_id)
    before_fail = before_metrics.failures[0] if before_metrics.failures else None
    after_fail = after_metrics.failures[0] if after_metrics.failures else None
    return FutureDiff(
        before_label=before_bundle.label,
        after_label=after_bundle.label,
        entries=entries,
        before_failure=describe_failure(scenario, before_fail),
        after_failure=describe_failure(scenario, after_fail),
        unknowns=[var.label for var in scenario.variables if var.epistemic_status.value == "UNKNOWN"],
    )


def _coverage(scenario: Scenario) -> CoverageReport:
    counts = {"resolved": 0, "estimated": 0, "inferred": 0, "unknown": 0}
    unknown_ids = []
    for var in scenario.variables:
        status = var.epistemic_status.value
        if status == "UNKNOWN":
            counts["unknown"] += 1
            unknown_ids.append(var.id)
        elif status == "ESTIMATED":
            counts["estimated"] += 1
        elif status == "INFERRED":
            counts["inferred"] += 1
        else:
            counts["resolved"] += 1
    if counts["unknown"] == 1:
        summary = "1 material unknown remains"
    elif counts["unknown"] == 0:
        summary = "No material unknowns remain in the declared world"
    else:
        summary = f"{counts['unknown']} material unknowns remain"
    return CoverageReport(unknown_ids=unknown_ids, summary=summary, percentage=None, **counts)


def _contract(plan_id: str, scenario: Scenario, repair: Any, spec: PlanSpec) -> FutureContract:
    actions = action_map(scenario)
    allowed = []
    for action_id in repair.action_ids:
        action = actions[action_id]
        allowed.append(
            ContractAction(
                action_id=action.id,
                action_type=action.action_type,
                resource=action.resource,
                max_cost=max(action.cost, 0),
            )
        )
    forbidden = [action.id for action in scenario.actions if action.id not in repair.action_ids]
    assumptions = []
    for var in scenario.variables:
        if var.role in {"fixed", "exogenous"} and var.distribution != "unknown":
            assumptions.append(
                Assumption(
                    id=f"asm-{var.id}",
                    description=var.label,
                    variable=var.id,
                    expected=var.baseline,
                )
            )
    created = datetime.now(timezone.utc)
    return FutureContract(
        contract_id=uuid.uuid4().hex[:16],
        plan_id=plan_id,
        approved_future_id=repair.id,
        created_at=created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=(created + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        goals=[goal.description for goal in spec.goals],
        invariants=[item.id for item in scenario.constraints if item.hardness == "hard"],
        assumptions=assumptions,
        allowed_actions=allowed,
        resource_scopes=sorted({item.resource for item in allowed}),
        spending_limit=max(100.0, repair.additional_cost),
        forbidden_actions=forbidden,
        verification_requirements=["provider.verify must match the approved effects"],
        compensation_actions=[action.id for action in scenario.actions if action.compensatable],
        provenance="user-approved-repair",
    )


def _reconcile(record: dict[str, Any]) -> dict[str, Any]:
    scenario: Scenario = record["scenario"]
    repair = next(item for item in record["repairs"] if item.id == record["recommended_id"])
    env = bind(scenario, effects_for(scenario, repair.action_ids), {})
    violations, unresolved, names = hard_status(scenario, evaluate_constraints(scenario, env))
    providers: SandboxProviders = record["providers"]
    flight = providers.state.get("bk_nyc", {})
    matched = violations == 0 and unresolved == 0
    if scenario.id == "travel":
        matched = matched and flight.get("day") == "friday" and flight.get("departure_min") == env["flight_departure_min"]
        matched = matched and providers.state["cal_exam"].get("moved") is not True
    return {
        "matched": matched,
        "message": "Observed state matches approved future" if matched else "Observed state does not match the approved future",
        "violations": names,
    }


def _inject_message(holds: bool, invalidated: list[str]) -> str:
    if not invalidated:
        return "No listed assumption changed."
    if holds:
        return "This assumption changed. The approved future still satisfies its invariants."
    return "This assumption changed. Future no longer valid."


def build_client():
    from pathlib import Path

    from shadow.llm.budget import BudgetLedger
    from shadow.llm.client import ResponseCache, model_client

    root = Path(__file__).resolve().parents[2]
    data = root / "data"
    return model_client(BudgetLedger(data / "budget.json"), ResponseCache(data / "cache.sqlite"))


def default_service(database_url: str = "sqlite://") -> PlanService:
    return PlanService(EventLog(database_url), build_client())
