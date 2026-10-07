"""Event-driven watch over approved futures. No polling loop."""

from __future__ import annotations

from typing import Any

from shadow.core.models import FutureContract, Scenario
from shadow.future_graph.build import build_graph
from shadow.repair.evaluate import evaluate_repairs, select_naive
from shadow.watcher.drift import affected_constraints, depends_on, unchanged, unknown_drift
from shadow.watcher.models import FutureDrift, WorldEvent


def _touches(scenario: Scenario, event: WorldEvent) -> bool:
    names = set(event.affected_entities) | set(event.payload.get("set_baseline") or {})
    return bool(names & {var.id for var in scenario.variables})


class FutureWatcher:
    def __init__(self, service: Any) -> None:
        self.service = service

    def process_event(self, event: WorldEvent, plan_id: str | None = None) -> list[FutureDrift]:
        records = self._records(plan_id)
        if event.epistemic_status == "UNKNOWN":
            drifts = []
            for record in records:
                contract = record.get("contract")
                drift = unknown_drift(contract if isinstance(contract, FutureContract) else None)
                record["last_drift"] = drift
                drifts.append(drift)
            return drifts or [unknown_drift(None)]
        if not records:
            return [unchanged(None, "No approved future is loaded.")]
        drifts = []
        for record in records:
            drifts.append(self._apply(record, event))
        return drifts

    def restore(self) -> int:
        loaded = 0
        for payload in self.service.events.load_approved():
            plan_id = payload["plan_id"]
            if plan_id in self.service.plans:
                continue
            scenario = Scenario.model_validate(payload["scenario"])
            contract = FutureContract.model_validate(payload["contract"])
            self.service.plans[plan_id] = {
                "id": plan_id,
                "text": payload.get("text") or "",
                "scenario_id": scenario.id,
                "seed": payload.get("seed") or 7,
                "status": contract.status,
                "stages": [],
                "contract": contract,
                "providers": self.service.plans.get(plan_id, {}).get("providers"),
                "scenario": scenario,
                "repairs": [],
                "skill_id": payload.get("skill_id"),
            }
            if self.service.plans[plan_id]["providers"] is None:
                from shadow.integrations.sandbox import SandboxProviders

                self.service.plans[plan_id]["providers"] = SandboxProviders()
            loaded += 1
        return loaded

    def _records(self, plan_id: str | None) -> list[dict[str, Any]]:
        if plan_id is not None:
            record = self.service.plans.get(plan_id)
            return [] if record is None else [record]
        return [
            record
            for record in self.service.plans.values()
            if isinstance(record.get("contract"), FutureContract)
            and record["contract"].status in {"ACTIVE", "REAFFIRMED"}
        ]

    def _apply(self, record: dict[str, Any], event: WorldEvent) -> FutureDrift:
        contract: FutureContract | None = record.get("contract")
        scenario: Scenario = record["scenario"]
        previous = "none" if contract is None else contract.status
        if not _touches(scenario, event) or (contract is not None and not depends_on(contract, scenario, event)):
            drift = unchanged(contract, "This world event does not affect the approved future.")
            record["last_drift"] = drift
            return drift
        updated = scenario.model_copy(deep=True)
        baseline = event.payload.get("set_baseline") or {}
        distribution = event.payload.get("set_distribution") or {}
        for var in updated.variables:
            if var.id in baseline:
                var.baseline = baseline[var.id]
            if var.id in distribution:
                var.distribution = distribution[var.id]
                if var.distribution == "point" and isinstance(var.baseline, (int, float)):
                    var.lower = float(var.baseline)
                    var.upper = float(var.baseline)
        record["scenario"] = updated
        invalidated = []
        if contract is None:
            repairs = evaluate_repairs(
                updated,
                [(bundle.id, bundle.label, bundle.action_ids, "catalog") for bundle in updated.bundles],
                seed=record.get("seed") or 7,
            )
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
            drift = unchanged(None, "World updated. No approved future was watching this plan.")
            record["last_drift"] = drift
            record["last_checked_at"] = event.observed_at
            return drift
        for assumption in contract.assumptions:
            if assumption.variable in baseline and baseline[assumption.variable] != assumption.expected:
                assumption.status = "invalidated"
                invalidated.append(assumption.variable)
                self.service.events.append(
                    record["id"],
                    "ASSUMPTION_INVALIDATED",
                    {"assumption": assumption.variable, "event": event.event_id},
                    event.provenance,
                )
        repairs = evaluate_repairs(
            updated,
            [(bundle.id, bundle.label, bundle.action_ids, "catalog") for bundle in updated.bundles],
            seed=record.get("seed") or 7,
        )
        approved = next((item for item in repairs if item.id == contract.approved_future_id), None)
        holds = bool(approved and approved.feasible)
        constraints = affected_constraints(updated, repairs, contract.approved_future_id)
        if not holds:
            contract.status = "STALE"
            record["status"] = "STALE"
            new_status = "INVALID"
            explanation = "Approved future is no longer valid. Authority revoked. Repair ready for approval."
            self.service.events.append(
                record["id"],
                "EXECUTION_HALTED",
                {"reason": "contract stale", "event": event.event_id},
                "watcher",
            )
        elif invalidated:
            contract.status = "REAFFIRMED"
            record["status"] = "REAFFIRMED"
            current = {var.id: var.baseline for var in updated.variables}
            for assumption in contract.assumptions:
                if assumption.variable in current and assumption.status == "invalidated":
                    assumption.expected = current[assumption.variable]
                    assumption.status = "updated"
            new_status = "DEGRADED"
            explanation = "World changed. Approved future still valid."
        else:
            new_status = "UNCHANGED"
            explanation = "World changed. Approved future still valid."
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
        record["last_drift"] = FutureDrift(
            contract_id=contract.contract_id,
            affected_assumptions=invalidated,
            affected_constraints=constraints,
            previous_status=previous,
            new_status=new_status,
            still_feasible=holds,
            repair_required=not holds,
            explanation=explanation,
            provenance=event.provenance,
        )
        record["last_checked_at"] = event.observed_at
        self.service.persist_contract(record)
        return record["last_drift"]
