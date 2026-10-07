"""Keep only LifeGraph records that share words with the plan."""

from __future__ import annotations

import re
from typing import Any

_WORD = re.compile(r"[a-z0-9']+")
_STOP = {"the", "and", "for", "with", "this", "that", "from", "your", "have", "will", "into", "about"}
_MATERIAL = ("cannot", "must", "fixed", "at most", "no more than", "do not", "confirmed")


def relevant_records(plan_text: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    needles = _tokens(plan_text)
    if not needles:
        return []
    kept = []
    for record in records:
        text = str(record.get("text") or "")
        material = any(marker in text.lower() for marker in _MATERIAL)
        if material or needles & _tokens(text):
            kept.append(record)
    return kept


def _tokens(text: str) -> set[str]:
    return {token for token in _WORD.findall(text.lower()) if len(token) > 3 and token not in _STOP}
