"""Compile a narrow candidate policy and compare it with the operator boundary.

OpenShell, when the prover is installed, is the system and network boundary.
It does not prove Shadow's semantic constraints. Those belong to the broker.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BOUNDARY_PATH = ROOT / "openshell" / "boundary.yaml"


class PolicyError(ValueError):
    pass


def load_boundary() -> dict[str, Any]:
    """Parse the operator boundary. The file is a small fixed YAML subset."""
    root: dict[str, Any] = {}
    section: str | None = None
    bucket: str | None = None
    for raw in BOUNDARY_PATH.read_text().splitlines():
        if not raw.strip():
            continue
        if not raw.startswith(" "):
            section = raw.split(":", 1)[0]
            root[section] = {}
            bucket = None
            continue
        stripped = raw.strip()
        if stripped.endswith(": []"):
            bucket = stripped.split(":", 1)[0]
            root[section][bucket] = []
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            bucket = stripped[:-1]
            root[section][bucket] = []
            continue
        if stripped.startswith("- ") and section and bucket is not None:
            root[section][bucket].append(stripped[2:].strip())
    return root


def candidate_policy(hosts: list[str]) -> dict[str, Any]:
    return {
        "filesystem": {"read": ["/tmp/shadow-data"], "write": ["/tmp/shadow-data"]},
        "process": {"exec": []},
        "network": {"allow": sorted(set(hosts))},
    }


def compare_policy(candidate: dict[str, Any], boundary: dict[str, Any] | None = None) -> dict[str, Any]:
    boundary = boundary or load_boundary()
    structural = _structural(candidate, boundary)
    prover = _run_prover(candidate, boundary)
    formal = (
        prover.get("result") == "within_boundary"
        and structural["status"] == "within_boundary"
        and set(prover.get("coverage") or []) >= set(structural["domains"])
    )
    return {
        "structural_status": structural["status"],
        "prover_status": prover.get("result", "prover_unavailable"),
        "prover_coverage": prover.get("coverage") or [],
        "domains": structural["domains"],
        "formally_verified": formal,
        "display": "FORMALLY VERIFIED" if formal else prover.get("result", "prover_unavailable"),
        "note": "OpenShell does not prove which calendar event or fare Shadow may change.",
    }


def _structural(candidate: dict[str, Any], boundary: dict[str, Any]) -> dict[str, Any]:
    required = ["filesystem", "process", "network"]
    if any(domain not in candidate for domain in required):
        return {"status": "unsupported", "domains": [key for key in candidate if key in required]}
    extra = [key for key in candidate if key not in boundary]
    if extra:
        return {"status": "unsupported", "domains": required}
    try:
        _contained(candidate["filesystem"]["read"], boundary["filesystem"]["read"])
        _contained(candidate["filesystem"]["write"], boundary["filesystem"]["write"])
        _contained(candidate["process"]["exec"], boundary["process"]["exec"])
        _contained(candidate["network"]["allow"], boundary["network"]["allow"])
    except PolicyError:
        return {"status": "outside_boundary", "domains": required}
    return {"status": "within_boundary", "domains": required}


def _contained(candidate: list[str], boundary: list[str]) -> None:
    allowed = set(boundary)
    for item in candidate:
        if item not in allowed and not any(item.startswith(prefix.rstrip("*")) for prefix in allowed if prefix.endswith("*")):
            # Exact match only unless the boundary entry is a prefix ending in *.
            if item not in allowed:
                raise PolicyError(item)


def _run_prover(candidate: dict[str, Any], boundary: dict[str, Any]) -> dict[str, Any]:
    binary = shutil.which("openshell-prover")
    if not binary:
        return {"result": "prover_unavailable", "coverage": []}
    try:
        completed = subprocess.run(
            [binary, "--format", "json"],
            input=json.dumps({"candidate": candidate, "boundary": boundary}),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"result": "error", "coverage": []}
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {"result": "error", "coverage": []}
    result = payload.get("result", "error")
    if result not in {"within_boundary", "outside_boundary", "unsupported", "inconclusive", "error"}:
        result = "error"
    return {"result": result, "coverage": payload.get("coverage") or []}
