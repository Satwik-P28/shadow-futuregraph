"""Lexical FTS, typed filters, and counterevidence. No embeddings."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from shadow.core.models import EpistemicStatus, Scenario, WorldFact

_TOKEN = re.compile(r"[a-z0-9]{3,}")


def retrieve(scenario: Scenario, query: str) -> dict[str, list[dict[str, Any]]]:
    ranked = _fts_rank(scenario.facts, query)
    return {
        "support": _public([fact for fact in ranked if "support" in fact.tags][:6]),
        "attack": _public([fact for fact in ranked if "attack" in fact.tags or "fixed" in fact.tags][:6]),
        "uncertainty": _public(
            [fact for fact in scenario.facts if fact.epistemic_status == EpistemicStatus.UNKNOWN]
        ),
        "counterevidence": _public(_counterevidence(scenario.facts)),
    }


def compact_context(scenario: Scenario, query: str) -> dict[str, Any]:
    """Typed context safe to send to a model. Raw source bodies are stripped."""
    found = retrieve(scenario, query)
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in found["support"] + found["attack"] + found["uncertainty"] + found["counterevidence"]:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        facts.append(item)
    return {
        "scenario_id": scenario.id,
        "plan": query,
        "bundles": [
            {"id": bundle.id, "label": bundle.label, "action_ids": bundle.action_ids, "rationale": bundle.rationale}
            for bundle in scenario.bundles
        ],
        "actions": [
            {"id": action.id, "action_type": action.action_type, "resource": action.resource, "label": action.label}
            for action in scenario.actions
        ],
        "constraints": [
            {"id": item.id, "label": item.label, "hardness": item.hardness, "description": item.description}
            for item in scenario.constraints
        ],
        "unknowns": [var.id for var in scenario.variables if var.epistemic_status == EpistemicStatus.UNKNOWN],
        "facts": facts,
    }


def _public(facts: list[WorldFact]) -> list[dict[str, Any]]:
    exported = []
    for fact in facts:
        exported.append(
            {
                "id": fact.id,
                "subject": fact.subject,
                "predicate": fact.predicate,
                "value": fact.value,
                "epistemic_status": fact.epistemic_status.value,
                "source_type": fact.source_type,
                "source_id": fact.source_id,
                "observed_at": fact.observed_at,
                "text": fact.text,
                "valid_from": fact.valid_from,
                "valid_to": fact.valid_to,
            }
        )
    return exported


def _fts_rank(facts: list[WorldFact], query: str) -> list[WorldFact]:
    tokens = _TOKEN.findall(query.lower())
    if not facts:
        return []
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE VIRTUAL TABLE facts USING fts5(id, body)")
    for fact in facts:
        connection.execute("INSERT INTO facts(id, body) VALUES (?, ?)", (fact.id, fact.text))
    by_id = {fact.id: fact for fact in facts}
    if not tokens:
        return list(facts)
    match = " OR ".join(tokens[:12])
    try:
        rows = connection.execute("SELECT id FROM facts WHERE facts MATCH ? LIMIT 12", (match,)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    ranked = [by_id[row[0]] for row in rows if row[0] in by_id]
    if ranked:
        return ranked
    return list(facts)


def _counterevidence(facts: list[WorldFact]) -> list[WorldFact]:
    grouped: dict[str, list[WorldFact]] = {}
    for fact in facts:
        grouped.setdefault(fact.subject, []).append(fact)
    conflicts: list[WorldFact] = []
    for group in grouped.values():
        values = {repr(fact.value) for fact in group}
        if len(values) > 1:
            conflicts.extend(group)
    return conflicts
