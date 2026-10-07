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
from shadow.futures.conflicts import cross_plan_conflicts, demo_pair
from shadow.futures.lab import material_controls, nearest_failure, simulate
from shadow.integrations.sandbox import SandboxProviders
from shadow.life.graph import project_life
from shadow.llm.client import FakeNemotronClient
from shadow.repair.evaluate import binding_for, evaluate_repairs, select_naive
from shadow.retrieval.engine import compact_context, retrieve
from shadow.runtime.broker import AuthorizationDenied, authorize
from shadow.runtime.events import EventLog
from shadow.runtime.execute import execute_bundle
from shadow.simulation.engine import bind, evaluate_constraints, hard_status
from shadow.skills.registry import SkillRegistry
from shadow.watcher.models import WorldEvent
from shadow.watcher.monitor import FutureWatcher
from shadow.world.compiler import SemanticProposal, attach_compiled, load_bundle
from shadow.world.loader import action_map, effects_for, load_scenario
from shadow.world.modelability import assess_freeform


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compiled_modelability(compiled: Any) -> dict[str, Any]:
    from shadow.world.modelability import ModelabilityResult

    status = {
        "READY": "SUPPORTED",
        "NEEDS_INFORMATION": "NEEDS_INFORMATION",
        "CONTRADICTORY": "CONTRADICTORY",
        "UNSUPPORTED": "UNSUPPORTED",
    }[compiled.status]
    return ModelabilityResult(
        status=status,
        reason=compiled.reason,
        missing_information=list(compiled.missing or compiled.contradictions),
        compiled_constraints=list(compiled.constraint_labels),
        compiled_dependencies=list(compiled.dependency_labels),
        provenance="executable primitive compiler",
    ).model_dump(mode="json")


class PlanService:
    def __init__(self, events: EventLog, client: Any | None = None, session_id: str | None = None) -> None:
        self.events = events
        self.client = client or FakeNemotronClient()
        self.session_id = session_id
        self.plans: dict[str, dict[str, Any]] = {}
        self.demo_futures = demo_pair()
        self.skills = SkillRegistry()
        self.watcher = FutureWatcher(self)
        self.watcher.restore()

    def _live_proposal(self, bundle: dict[str, Any] | None) -> SemanticProposal | None:
        import os

        from shadow.life.retrieve import relevant_records
        from shadow.world.routing import study_compile_model

        if bundle is None or os.environ.get("NEBIUS_LIVE") != "1":
            return None
        model = study_compile_model()
        if model is None:
            return None
        context = {
            "plan_text": bundle.get("plan_text") or "",
            "records": relevant_records(str(bundle.get("plan_text") or ""), list(bundle.get("records") or [])),
        }
        try:
            try:
                proposal = self.client.complete_json("compile_world", context, SemanticProposal, model=model)
            except TypeError:
                proposal = self.client.complete_json("compile_world", context, SemanticProposal)
        except Exception:
            return None
        return proposal if isinstance(proposal, SemanticProposal) else None

    def create(self, text: str, scenario_id: str = "travel", seed: int = 7) -> dict[str, Any]:
        plan_id = uuid.uuid4().hex[:12]
        bundle = load_bundle(scenario_id)
        scenario, compiled = attach_compiled(load_scenario(scenario_id), self._live_proposal(bundle))
        record = {
            "id": plan_id,
            "text": text,
            "scenario_id": scenario_id,
            "seed": seed,
            "status": "CREATED",
            "stages": [],
            "contract": None,
            "providers": SandboxProviders(),
            "scenario": scenario,
            "compiled_from": None if compiled is None else "calendar, email, reservation, preferences",
            "skill_id": None if (skill := self.skills.available_for(text)) is None else skill.id,
        }
        self.plans[plan_id] = record
        self.events.append(plan_id, "PLAN_CREATED", {"scenario_id": scenario_id}, "user")
        return {"id": plan_id, "status": "CREATED"}

    def analyze_freeform(self, text: str, demo_context_id: str | None = None, seed: int = 7) -> dict[str, Any]:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Enter what you are planning.")
        if demo_context_id not in {None, "travel", "apartment"}:
            raise ValueError("Unknown example context.")
        if demo_context_id is None:
            from shadow.world.executable import compile_primitives

            compiled = compile_primitives(
                cleaned,
                [{"id": "user_plan", "text": cleaned, "observed_at": "1970-01-01T00:00:00Z"}],
            )
            if compiled.status == "READY" and compiled.scenario is not None:
                view = self.open_compiled(cleaned, compiled.scenario, seed)
                return {"modelability": _compiled_modelability(compiled), "plan": view}
            if compiled.status in {"NEEDS_INFORMATION", "CONTRADICTORY"}:
                return {"modelability": _compiled_modelability(compiled), "plan": None}
        result = assess_freeform(cleaned, demo_context_id)
        if result.status != "SUPPORTED" or demo_context_id is None:
            return {"modelability": result.model_dump(mode="json"), "plan": None}
        created = self.create(text, demo_context_id, seed)
        view = self.analyze(created["id"])
        view["modelability"] = result.model_dump(mode="json")
        return {"modelability": result.model_dump(mode="json"), "plan": view}

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
        record["future_summary"] = _future_summary(record)
        return self.view(plan_id)

    def open_compiled(self, text: str, scenario: Scenario, seed: int = 7) -> dict[str, Any]:
        """Run search on a world the executable compiler produced. Not a fixture."""
        plan_id = uuid.uuid4().hex[:12]
        record = {
            "id": plan_id,
            "text": text,
            "scenario_id": scenario.id,
            "seed": seed,
            "status": "CREATED",
            "stages": [],
            "contract": None,
            "providers": SandboxProviders(),
            "scenario": scenario,
            "compiled_from": "executable primitive compiler",
            "skill_id": None,
        }
        self.plans[plan_id] = record
        self.events.append(plan_id, "PLAN_CREATED", {"scenario_id": scenario.id, "route": "executable"}, "compiler")
        return self.analyze(plan_id)

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
        self.persist_contract(record)
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
            authorize(contract, action, {"scenario": record["scenario"]})
        except AuthorizationDenied as exc:
            self.events.append(plan_id, "ACTION_BLOCKED", {"action_id": action_id, "reason": exc.reason}, "broker")
            return {"authorized": False, "message": "Blocked: action is outside the approved future."}
        return {"authorized": True, "message": "authorized"}

    def inject(self, plan_id: str, event_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        scenario: Scenario = record["scenario"]
        event = next(item for item in scenario.events if item.id == event_id)
        world_event = WorldEvent(
            event_id=event.id,
            source="demo",
            event_type=event.id,
            observed_at=_now(),
            affected_entities=list(event.set_baseline),
            payload={"set_baseline": event.set_baseline, "set_distribution": event.set_distribution},
            epistemic_status="VERIFIED",
            provenance="demo-injection",
        )
        matched = self.skills.available_for(record["text"], event.id)
        record["skill_id"] = None if matched is None else matched.id
        drift = self.watcher.process_event(world_event, plan_id=plan_id)[0]
        contract: FutureContract | None = record.get("contract")
        holds = drift.still_feasible is True
        if record.get("naive_id") and record.get("recommended_id"):
            record["diff"] = _diff(record["scenario"], record["naive_id"], record["recommended_id"], record.get("repairs") or [])
        skill = self.skills.get(record["skill_id"]) if record.get("skill_id") else None
        return {
            "event": event.model_dump(mode="json"),
            "invalidated": drift.affected_assumptions,
            "approved_future_holds": holds,
            "contract_status": None if contract is None else contract.status,
            "authority": "revoked" if contract and contract.status == "STALE" else "active",
            "recommended_repair_id": record.get("recommended_id"),
            "message": _inject_message(holds, drift.affected_assumptions),
            "drift_status": drift.new_status,
            "watch_message": drift.explanation,
            "skill_name": None if skill is None else skill.name,
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
            "compiled_from": record.get("compiled_from"),
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
            "watch": _watch(record, self.skills),
            "memory": _memory(record["scenario"]),
            "life": None if record.get("future_summary") is None else record["future_summary"]["life"],
            "future": None if record.get("future_summary") is None else _public_future(record["future_summary"]),
            "no_feasible_message": None
            if record["status"] != "NO_FEASIBLE_FUTURE"
            else "No feasible future found under the current hard constraints.",
        }

    def persist_contract(self, record: dict[str, Any]) -> None:
        contract: FutureContract | None = record.get("contract")
        if contract is None:
            return
        self.events.save_approved(
            contract.contract_id,
            record["id"],
            contract.status,
            {
                "plan_id": record["id"],
                "text": record.get("text"),
                "seed": record.get("seed") or 7,
                "skill_id": record.get("skill_id"),
                "contract": contract.model_dump(mode="json"),
                "scenario": record["scenario"].model_dump(mode="json"),
                "session_id": self.session_id,
            },
        )

    def lab_controls(self, plan_id: str) -> dict[str, Any]:
        record = self._ready(plan_id)
        return {"variables": material_controls(record["scenario"]), "simulation": True}

    def simulate_lab(self, plan_id: str, overrides: dict[str, Any], repair_id: str | None = None) -> dict[str, Any]:
        record = self._ready(plan_id)
        repair = self._repair(record, repair_id)
        return simulate(record["scenario"], repair.action_ids, overrides)

    def nearest_lab(self, plan_id: str, repair_id: str | None = None) -> dict[str, Any]:
        record = self._ready(plan_id)
        repair = self._repair(record, repair_id)
        return nearest_failure(record["scenario"], repair)

    def list_futures(self) -> dict[str, Any]:
        summaries = [record["future_summary"] for record in self.plans.values() if record.get("future_summary")]
        summaries.extend(self.demo_futures)
        futures = [_public_future(item) for item in summaries]
        return {"futures": futures, "conflicts": cross_plan_conflicts(summaries)}

    def reset_demo(self) -> dict[str, Any]:
        self.plans.clear()
        self.events.clear_approved(self.session_id)
        self.demo_futures = demo_pair()
        created = self.create(
            "Move my NYC trip to Friday and make sure everything still works.",
            "travel",
            7,
        )
        return self.analyze(created["id"])

    def receipt(self, plan_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        events = self.events.list_for(plan_id)
        contract = record.get("contract")
        reconciliation = record.get("reconciliation")
        coverage = record.get("coverage")
        return {
            "approved": record.get("recommended_id"),
            "executed": [event.payload.get("action_id") for event in events if event.event_type == "ACTION_EXECUTED"],
            "blocked": [event.payload.get("action_id") for event in events if event.event_type == "ACTION_BLOCKED"],
            "verification": None if reconciliation is None else reconciliation.get("message"),
            "matched": None if reconciliation is None else reconciliation.get("matched"),
            "unknowns": [] if coverage is None else coverage.unknown_ids,
            "contract_status": None if contract is None else contract.status,
        }

    def _ready(self, plan_id: str) -> dict[str, Any]:
        record = self.plans[plan_id]
        if not record.get("repairs"):
            raise ValueError("Analyze the plan before simulating it.")
        return record

    def _repair(self, record: dict[str, Any], repair_id: str | None):
        chosen = repair_id or record.get("recommended_id")
        repair = next((item for item in record["repairs"] if item.id == chosen), None)
        if repair is None:
            raise ValueError("No repair is selected.")
        return repair

    def personal_status(self) -> dict[str, Any]:
        import os

        watched = [
            record
            for record in self.plans.values()
            if isinstance(record.get("contract"), FutureContract) and record["contract"].status in {"ACTIVE", "REAFFIRMED"}
        ]
        counts: dict[str, int] = {}
        for record in self.plans.values():
            for fact in record["scenario"].facts:
                if fact.memory_kind:
                    counts[fact.memory_kind] = counts.get(fact.memory_kind, 0) + 1
        search = "LIVE" if os.environ.get("TAVILY_API_KEY") else "OFF"
        return {
            "monitoring_active": bool(watched),
            "approved_futures_watched": len(watched),
            "memory_counts": counts,
            "skills": [item.name for item in self.skills.list_skills()],
            "connected_tools": {"calendar": "SANDBOX", "mail": "SANDBOX", "travel": "SANDBOX", "search": search},
            "privacy": {
                "personal_world_model": "local",
                "raw_source_bodies_sent_to_model": False,
                "structured_facts_sent_to_nemotron": True,
                "real_actions_enabled": os.environ.get("SHADOW_REAL_ACTIONS_ENABLED", "false").lower() == "true",
            },
            "mode": "SANDBOX",
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


def _future_summary(record: dict[str, Any]) -> dict[str, Any]:
    scenario: Scenario = record["scenario"]
    recommended = next((item for item in record.get("repairs", []) if item.recommended), None)
    coverage = record.get("coverage")
    unknowns = 0 if coverage is None else coverage.unknown
    failure = None if recommended is None or not recommended.failures else recommended.failures[0]
    effects = {} if recommended is None else effects_for(scenario, recommended.action_ids)
    return {
        "future_id": record["id"],
        "plan_id": record["id"],
        "name": record["text"],
        "status": _future_status(record, recommended, unknowns),
        "material_unknowns": unknowns,
        "nearest_failure": describe_failure(scenario, failure),
        "scenario_id": record["scenario_id"],
        "effects": effects,
        "linked_entities": [fact.id for fact in scenario.facts],
        "life": project_life(scenario, record["text"]),
    }


def _public_future(summary: dict[str, Any]) -> dict[str, Any]:
    hidden = {"effects", "linked_entities", "claims", "life"}
    return {key: value for key, value in summary.items() if key not in hidden}


def _future_status(record: dict[str, Any], recommended: Any, unknowns: int) -> str:
    contract = record.get("contract")
    if contract is not None and contract.status == "STALE":
        return "DRIFT DETECTED"
    reconciliation = record.get("reconciliation")
    if reconciliation and reconciliation.get("matched"):
        return "VERIFIED"
    if contract is not None and contract.status == "COMPLETED":
        return "EXECUTED"
    if record.get("status") == "NO_FEASIBLE_FUTURE":
        return "UNKNOWN"
    if recommended is not None and recommended.failures:
        return "FRAGILE"
    if unknowns:
        return "UNKNOWN"
    if contract is not None and contract.status in {"ACTIVE", "REAFFIRMED"}:
        return "MONITORING"
    return "HEALTHY"


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


def _watch(record: dict[str, Any], skills: SkillRegistry) -> dict[str, Any]:
    contract: FutureContract | None = record.get("contract")
    monitoring = contract is not None and contract.status in {"ACTIVE", "REAFFIRMED", "COMPLETED"}
    drift = record.get("last_drift")
    skill = skills.get(record["skill_id"]) if record.get("skill_id") in {item.id for item in skills.list_skills()} else None
    return {
        "monitoring": monitoring,
        "approved_futures": 1 if monitoring else 0,
        "last_checked_at": record.get("last_checked_at"),
        "drift_status": None if drift is None else drift.new_status,
        "message": None if drift is None else drift.explanation,
        "skill_name": None if skill is None else skill.name,
    }


def _memory(scenario: Scenario) -> dict[str, str] | None:
    fact = next((item for item in scenario.facts if item.memory_kind == "COMMITMENT"), None)
    if fact is None:
        fact = next((item for item in scenario.facts if item.memory_kind == "PREFERENCE"), None)
    if fact is None:
        return None
    source = "Previous decision / saved commitment" if fact.memory_kind == "COMMITMENT" else "Preference memory"
    label = "Dinner is protected" if fact.subject == "dinner" else fact.text
    return {"label": label, "source": source}


def _inject_message(holds: bool, invalidated: list[str]) -> str:
    if not invalidated:
        return "No listed assumption changed."
    if holds:
        return "This assumption changed. The approved future still satisfies its invariants."
    return "This assumption changed. Future no longer valid."


def build_client():
    from shadow.llm.budget import BudgetLedger
    from shadow.llm.client import ResponseCache, model_client
    from shadow.paths import repo_root

    root = repo_root()
    data = root / "data"
    return model_client(BudgetLedger(data / "budget.json"), ResponseCache(data / "cache.sqlite"))


def default_service(database_url: str = "sqlite://") -> PlanService:
    return PlanService(EventLog(database_url), build_client())
