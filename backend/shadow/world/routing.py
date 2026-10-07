"""Choose a compiler architecture from measured summaries. No model call."""

from __future__ import annotations

import json
from typing import Any

from shadow.paths import repo_root

ARCHITECTURES = (
    "lightning",
    "lightning_audit",
    "super",
    "super_audit",
)

LIGHTNING_MODEL = "nvidia/Nemotron-3_5-Lightning"
SUPER_MODEL = "nvidia/nemotron-3-super-120b-a12b"


def select_architecture(summaries: dict[str, dict[str, Any]]) -> str:
    """Prefer fewer false hard constraints, then recall, unknowns, repair, then cost."""
    names = [name for name in ARCHITECTURES if name in summaries]
    if not names:
        raise ValueError("no compiler summaries")
    best_false = min(float(summaries[name]["false_hard_rate"]) for name in names)
    eligible = [name for name in names if float(summaries[name]["false_hard_rate"]) <= best_false + 0.05]

    def sort_key(name: str) -> tuple[float, float, float, float, int]:
        item = summaries[name]
        return (
            float(item["hard_recall"]),
            float(item["unknown_rate"]),
            float(item["repair_rate"]),
            -float(item["cost_usd"]),
            -names.index(name),
        )

    return max(eligible, key=sort_key)


def model_for_architecture(architecture: str) -> str:
    if architecture.startswith("super"):
        return SUPER_MODEL
    return LIGHTNING_MODEL


def study_compile_model() -> str | None:
    path = repo_root() / "shadowbench" / "compiler-study" / "decision.json"
    if not path.exists():
        return None
    decision = json.loads(path.read_text())
    architecture = str(decision.get("architecture") or "")
    if architecture not in ARCHITECTURES:
        return None
    return model_for_architecture(architecture)


def should_escalate(bundle: dict[str, Any], compiled_labels: list[str], audit_types: list[str]) -> bool:
    """Observable escalation. Model self-confidence is not an input."""
    records = [str(item.get("text") or "") for item in bundle.get("records") or []]
    lowered = [text.lower() for text in records]
    conflicting = any("cannot" in text or "must" in text for text in lowered) and any(
        "please move" in text or "ignore the earlier" in text for text in lowered
    )
    unknown = any("unknown" in text or "not confirmed" in text or "whether" in text for text in lowered)
    disagreement = any(kind in {"MISSED_CONSTRAINT", "UNSUPPORTED_CONSTRAINT", "CONTRADICTION", "SHOULD_BE_UNKNOWN"} for kind in audit_types)
    missing = any(not label for label in compiled_labels)
    irreversible = any(token in " ".join(lowered) for token in ("cancel", "charge", "nonrefundable"))
    return conflicting or unknown or disagreement or missing or irreversible
