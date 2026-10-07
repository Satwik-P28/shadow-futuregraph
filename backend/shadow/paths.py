"""Find the repo root in a checkout and inside the Docker image."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    override = os.environ.get("SHADOW_ROOT")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "fixtures" / "travel" / "world.json").exists():
            return parent
    return here.parents[3]
