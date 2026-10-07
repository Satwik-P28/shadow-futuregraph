"""Project a scenario's facts into a persistent life graph.

Inferred links stay INFERRED. Facts keep the epistemic status they already have.
"""

from __future__ import annotations

from shadow.core.models import Scenario

_KIND = {
    "COMMITMENT": "Commitment",
    "PREFERENCE": "Preference",
    "RESERVATION": "Reservation",
    "RELATIONSHIP": "Person",
    "RESPONSIBILITY": "Responsibility",
    "DECISION": "Decision",
    "APPROVED_FUTURE": "Future",
}


def project_life(scenario: Scenario, plan_text: str) -> dict[str, object]:
    nodes = [
        {
            "id": "plan",
            "kind": "Plan",
            "label": plan_text,
            "epistemic_status": "VERIFIED",
            "source": "user",
            "privacy_label": "personal",
        }
    ]
    edges = []
    for fact in scenario.facts:
        kind = _KIND.get(fact.memory_kind or "", "Event")
        nodes.append(
            {
                "id": fact.id,
                "kind": kind,
                "label": fact.text,
                "epistemic_status": fact.epistemic_status.value,
                "source": fact.source_id,
                "observed_at": fact.observed_at,
                "privacy_label": fact.privacy_label,
            }
        )
        relation = "HAS_COMMITMENT" if fact.memory_kind == "COMMITMENT" else "DEPENDS_ON"
        edges.append(
            {
                "source": "plan",
                "target": fact.id,
                "relation": relation,
                "epistemic_status": "INFERRED",
            }
        )
    return {"nodes": nodes, "edges": edges}
