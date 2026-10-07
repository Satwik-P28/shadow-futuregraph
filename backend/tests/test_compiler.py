from shadow.benchmark.adversarial import evaluate_case, load_cases, summarize
from shadow.pipeline import PlanService
from shadow.runtime.events import EventLog
from shadow.world.compiler import compile_bundle, load_bundle


def test_hero_context_licenses_constraints_without_naming_a_flight():
    bundle = load_bundle("travel")
    assert bundle is not None
    compiled = compile_bundle(bundle)
    labels = " ".join(item.label for item in compiled.items())
    assert "11:20" not in labels
    assert "c_dinner" in compiled.licensed_constraint_ids
    assert "c_budget" in compiled.licensed_constraint_ids
    assert "c_exam" in compiled.licensed_constraint_ids
    dinner = next(item for item in compiled.hard_constraints if item.id == "dinner_deadline")
    assert dinner.value == 19 * 60
    assert dinner.epistemic_status.value == "COMPUTED"
    unknown = next(item for item in compiled.unknowns if item.id == "street_closure")
    assert unknown.epistemic_status.value == "UNKNOWN"
    assert all(item.epistemic_status.value != "VERIFIED" or item.id == "hotel_hold" for item in compiled.items())
    service = PlanService(EventLog())
    created = service.create("Move my NYC trip to Friday and make sure everything still works.", "travel")
    view = service.analyze(created["id"])
    assert view["recommended_repair_id"] == "b1120"
    assert view["compiled_from"] == "calendar, email, reservation, preferences"


def test_model_proposal_cannot_promote_itself():
    from shadow.world.compiler import proposal_from_payload, score_compilation

    proposal = proposal_from_payload(
        {
            "hard_constraints": [{"label": "cannot move", "source_ids": ["cal"], "status": "VERIFIED", "confidence": 0.99, "value": 11}],
            "soft_preferences": [],
            "dependencies": [{"label": "ride affects flight", "source_ids": ["res"], "status": "VERIFIED"}],
            "unknowns": [{"label": "street closure", "status": "VERIFIED"}],
        }
    )
    assert proposal.hard_constraints[0]["status"] == "INFERRED"
    assert "confidence" not in proposal.hard_constraints[0]
    compiled = compile_bundle(
        {"plan_text": "Keep Friday.", "records": [{"id": "cal", "kind": "calendar", "text": "Design review cannot move."}]},
        proposal,
    )
    assert all(item.epistemic_status.value != "VERIFIED" or item.validated for item in compiled.hard_constraints)
    scored = score_compilation(
        compiled,
        {"hard": ["cannot move"], "not_hard": [], "dependencies": ["ride"], "not_dependencies": [], "unknowns": ["street"], "repair": "keep"},
    )
    assert scored["hard_hit"] >= 1
    assert scored["unknown_hit"] == 1


def test_adversarial_holdout_is_ten_frozen_cases():
    cases = load_cases()
    assert len(cases) == 10
    summary = summarize([evaluate_case(case) for case in cases])
    assert summary["shadow_task"].endswith("/10")
    assert summary["failure_recall"]
