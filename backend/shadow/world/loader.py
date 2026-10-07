"""Load domain fixtures. The core never branches on scenario id."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from shadow.core.models import ActionDef, Bundle, Scenario

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures"


def scenario_path(scenario_id: str) -> Path:
    path = FIXTURES / scenario_id / "world.json"
    if not path.exists():
        raise FileNotFoundError(f"unknown scenario: {scenario_id}")
    return path


@lru_cache(maxsize=16)
def load_scenario(scenario_id: str) -> Scenario:
    data = json.loads(scenario_path(scenario_id).read_text())
    return Scenario.model_validate(data)


def action_map(scenario: Scenario) -> dict[str, ActionDef]:
    return {action.id: action for action in scenario.actions}


def bundle_map(scenario: Scenario) -> dict[str, Bundle]:
    return {bundle.id: bundle for bundle in scenario.bundles}


def effects_for(scenario: Scenario, action_ids: list[str]) -> dict[str, object]:
    actions = action_map(scenario)
    merged: dict[str, object] = {}
    for action_id in action_ids:
        action = actions.get(action_id)
        if action is None:
            raise KeyError(action_id)
        merged.update(action.effects)
    return merged


def bundle_cost(scenario: Scenario, action_ids: list[str]) -> float:
    actions = action_map(scenario)
    return float(sum(actions[action_id].cost for action_id in action_ids if action_id in actions))
