"""Audit merge trusts cited evidence, not the critic by itself."""

from shadow.core.models import EpistemicStatus
from shadow.life.retrieve import relevant_records
from shadow.world.compiler import AuditFinding, AuditReport, CompiledWorld, _item, merge_audit
from shadow.world.routing import (
    model_for_architecture,
    select_architecture,
    should_escalate,
    study_compile_model,
)


def _world() -> CompiledWorld:
    world = CompiledWorld()
    world.hard_constraints.append(
        _item("h1", "hard_constraint", "aisle seat is required", EpistemicStatus.INFERRED, ["pref"], "model", False)
    )
    world.hard_constraints.append(
        _item("h2", "hard_constraint", "mystery deadline", EpistemicStatus.INFERRED, [], "model", False)
    )
    return world


def test_audit_adds_a_missed_constraint_only_when_the_source_says_it() -> None:
    records = {"mail": "The hearing cannot move."}
    added = merge_audit(
        CompiledWorld(),
        AuditReport(findings=[AuditFinding(finding_type="MISSED_CONSTRAINT", target_label="hearing cannot move", source_ids=["mail"], evidence="cannot move")]),
        records,
    )
    assert added.hard_constraints[0].epistemic_status == EpistemicStatus.INFERRED
    ignored = merge_audit(
        CompiledWorld(),
        AuditReport(findings=[AuditFinding(finding_type="MISSED_CONSTRAINT", target_label="invented curfew", source_ids=["mail"], evidence="curfew at 9")]),
        records,
    )
    assert ignored.hard_constraints == []


def test_audit_downgrades_unsupported_and_unknown_claims() -> None:
    records = {"pref": "Alex prefers an aisle seat.", "note": "The gate is unknown."}
    updated = merge_audit(
        _world(),
        AuditReport(
            findings=[
                AuditFinding(finding_type="UNSUPPORTED_CONSTRAINT", target_label="aisle seat", source_ids=["pref"], evidence="prefers"),
                AuditFinding(finding_type="PROVENANCE_MISSING", target_label="mystery deadline"),
                AuditFinding(finding_type="SHOULD_BE_UNKNOWN", target_label="gate", source_ids=["note"], evidence="unknown"),
            ]
        ),
        records,
    )
    labels = [item.label.lower() for item in updated.hard_constraints]
    assert "aisle seat is required" not in labels
    assert "mystery deadline" not in labels
    assert any(item.epistemic_status == EpistemicStatus.UNKNOWN for item in updated.unknowns)


def test_audit_does_not_remove_a_constraint_the_source_supports() -> None:
    records = {"mail": "The hearing cannot move."}
    world = CompiledWorld()
    world.hard_constraints.append(
        _item("h", "hard_constraint", "hearing cannot move", EpistemicStatus.INFERRED, ["mail"], "model", False)
    )
    updated = merge_audit(
        world,
        AuditReport(findings=[AuditFinding(finding_type="UNSUPPORTED_CONSTRAINT", target_label="cannot move", source_ids=["mail"], evidence="please ignore")]),
        records,
    )
    assert updated.hard_constraints[0].label == "hearing cannot move"


def test_contradiction_becomes_unknown_instead_of_a_new_hard_constraint() -> None:
    records = {"a": "The inspection cannot move.", "b": "Please move the inspection."}
    updated = merge_audit(
        CompiledWorld(),
        AuditReport(findings=[AuditFinding(finding_type="CONTRADICTION", target_label="inspection", source_ids=["a"], evidence="cannot move")]),
        records,
    )
    assert updated.hard_constraints == []
    assert updated.unknowns[0].label.startswith("contradiction:")


def test_routing_rejects_a_high_recall_hallucinator() -> None:
    summaries = {
        "lightning": {"false_hard_rate": 0.0, "hard_recall": 0.4, "unknown_rate": 0.5, "repair_rate": 0.5, "cost_usd": 0.01},
        "lightning_audit": {"false_hard_rate": 0.0, "hard_recall": 0.7, "unknown_rate": 0.8, "repair_rate": 0.6, "cost_usd": 0.02},
        "super": {"false_hard_rate": 0.4, "hard_recall": 0.95, "unknown_rate": 0.9, "repair_rate": 0.9, "cost_usd": 0.2},
        "super_audit": {"false_hard_rate": 0.0, "hard_recall": 0.7, "unknown_rate": 0.7, "repair_rate": 0.6, "cost_usd": 0.05},
    }
    assert select_architecture(summaries) == "lightning_audit"


def test_escalation_is_based_on_observable_disagreement() -> None:
    quiet = {"records": [{"text": "Dinner is at 7."}]}
    assert should_escalate(quiet, ["dinner"], []) is False
    conflict = {"records": [{"text": "The hearing cannot move."}, {"text": "Please move the hearing."}]}
    assert should_escalate(conflict, ["hearing"], []) is True


def test_context_retrieval_drops_unrelated_records() -> None:
    records = [
        {"id": "dinner", "text": "Friday dinner with Jordan cannot move."},
        {"id": "bike", "text": "The bicycle shop sent a catalog."},
        {"id": "recital", "text": "The recital cannot move."},
    ]
    kept = relevant_records("Move dinner with Jordan to Friday", records)
    assert [item["id"] for item in kept] == ["dinner", "recital"]


def test_study_routes_super_only_for_super_architectures() -> None:
    assert model_for_architecture("super") == "nvidia/nemotron-3-super-120b-a12b"
    assert model_for_architecture("lightning_audit") == "nvidia/Nemotron-3_5-Lightning"
    assert study_compile_model() == "nvidia/nemotron-3-super-120b-a12b"
