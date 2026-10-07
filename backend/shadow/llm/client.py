"""One Token Factory client. Paid calls require NEBIUS_LIVE=1 and a reservation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from shadow.core.models import PlanSpec, RepairProposal
from shadow.llm.budget import BudgetError, BudgetLedger
from shadow.llm.pricing import DEFAULT_BASE_URL, DEFAULT_MODEL, cost_usd, estimate_tokens

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
# Output caps were chosen before the live pilot. PlanSpec needs the higher cap.
PURPOSE_TOKENS = {
    "analyze_plan": ("analyze_plan.txt", 512),
    "propose_repairs": ("propose_repairs.txt", 512),
    "direct_choice": ("direct_choice.txt", 256),
    "plan_choice": ("plan_choice.txt", 256),
    "critique_choice": ("critique_choice.txt", 256),
    "compile_world": ("compile_world.txt", 512),
}


class LiveDisabled(RuntimeError):
    pass


class SchemaError(RuntimeError):
    pass


def prompt_text(name: str) -> str:
    return (PROMPT_DIR / name).read_text()


def prompt_hash(name: str) -> str:
    return hashlib.sha256(prompt_text(name).encode()).hexdigest()[:16]


def _messages_hash(model: str, messages: list[dict[str, str]], params: dict[str, Any], version: str) -> str:
    blob = json.dumps({"model": model, "messages": messages, "params": params, "version": version}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class ResponseCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
        )

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT payload FROM cache WHERE key = ?", (key,)).fetchone()
        return None if row is None else json.loads(row[0])

    def put(self, key: str, payload: dict[str, Any]) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO cache(key, payload, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(payload), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        self._db.commit()


def _schema_detail(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors():
            loc = ".".join(str(item) for item in err.get("loc", ()))
            parts.append(f"{loc}:{err.get('type')}")
        return "schema invalid: " + ", ".join(parts[:8])
    return "model output was not JSON"


def coerce_payload(schema: type[BaseModel], payload: dict[str, Any]) -> dict[str, Any]:
    """One local shape repair. Does not call the model again and does not invent probabilities."""
    if schema.__name__ == "PlanSpec":
        return _coerce_plan(payload)
    if schema.__name__ == "RepairProposal":
        return _coerce_repairs(payload)
    if schema.__name__ == "ChoiceSpec":
        return _coerce_choice(payload)
    if schema.__name__ == "SemanticProposal":
        from shadow.world.compiler import proposal_from_payload

        return proposal_from_payload(payload).model_dump()
    return payload


def _coerce_plan(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    data["goals"] = [_as_goal(item, index) for index, item in enumerate(_as_list(data.get("goals")))]
    data["hard_constraints"] = [
        _as_constraint(item, index, "hard") for index, item in enumerate(_as_list(data.get("hard_constraints")))
    ]
    data["soft_preferences"] = [
        _as_constraint(item, index, "soft") for index, item in enumerate(_as_list(data.get("soft_preferences")))
    ]
    data["dependencies"] = [_as_dependency(item, index) for index, item in enumerate(_as_list(data.get("dependencies")))]
    data["uncertain_variables"] = [
        _as_uncertain(item, index) for index, item in enumerate(_as_list(data.get("uncertain_variables")))
    ]
    data["unknowns"] = [str(item) for item in _as_list(data.get("unknowns"))]
    data["hazards"] = [_as_hazard(item, index) for index, item in enumerate(_as_list(data.get("hazards")))]
    if "intended_bundle_id" not in data:
        data["intended_bundle_id"] = None
    return data


def _coerce_repairs(payload: dict[str, Any]) -> dict[str, Any]:
    repairs = []
    for index, item in enumerate(_as_list(payload.get("repairs"))):
        if isinstance(item, str):
            repairs.append({"id": f"r{index}", "label": item, "action_ids": [], "rationale": item})
        elif isinstance(item, dict):
            row = dict(item)
            row.setdefault("id", f"r{index}")
            row.setdefault("label", row["id"])
            row.setdefault("rationale", "")
            if isinstance(row.get("action_ids"), str):
                row["action_ids"] = [row["action_ids"]]
            row.setdefault("action_ids", [])
            repairs.append(row)
    return {"repairs": repairs}


def _coerce_choice(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    if data.get("bundle_id") in {"", "null", "none", "None"}:
        data["bundle_id"] = None
    data["hazards"] = [str(item) for item in _as_list(data.get("hazards"))]
    data["unknowns"] = [str(item) for item in _as_list(data.get("unknowns"))]
    if data.get("confidence") in {"", "null", "none", "None"}:
        data["confidence"] = None
    return data


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_goal(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        row = dict(item)
        row.setdefault("id", f"g{index}")
        row.setdefault("description", str(row.get("text") or row["id"]))
        return row
    return {"id": f"g{index}", "description": str(item)}


def _as_constraint(item: Any, index: int, hardness: str) -> dict[str, Any]:
    if isinstance(item, dict):
        row = dict(item)
        row.setdefault("id", f"c{index}")
        row.setdefault("description", str(row.get("text") or row["id"]))
        if row.get("hardness") not in {"hard", "soft"}:
            row["hardness"] = hardness
        row["epistemic_status"] = _status(row.get("epistemic_status"))
        return row
    return {"id": f"c{index}", "description": str(item), "hardness": hardness, "epistemic_status": "INFERRED"}


def _as_dependency(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        row = dict(item)
        row.setdefault("id", f"d{index}")
        row.setdefault("source", "plan")
        row.setdefault("target", "goal")
        row.setdefault("relation", "DEPENDS_ON")
        row.setdefault("rationale", "")
        row["epistemic_status"] = _status(row.get("epistemic_status") or "INFERRED")
        return row
    return {
        "id": f"d{index}",
        "source": "plan",
        "target": "goal",
        "relation": "DEPENDS_ON",
        "rationale": str(item),
        "epistemic_status": "INFERRED",
    }


def _as_uncertain(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        row = dict(item)
        row.setdefault("id", f"u{index}")
        row.setdefault("description", str(row.get("text") or row["id"]))
        row.setdefault("why_material", row["description"])
        return row
    return {"id": str(item), "description": str(item), "why_material": "The model marked this as uncertain."}


def _as_hazard(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        row = dict(item)
        row.setdefault("id", f"h{index}")
        row.setdefault("description", str(row.get("text") or row["id"]))
        if isinstance(row.get("related_variables"), str):
            row["related_variables"] = [row["related_variables"]]
        row.setdefault("related_variables", [])
        return row
    return {"id": f"h{index}", "description": str(item), "related_variables": []}


def _status(value: Any) -> str:
    text = str(value or "INFERRED").upper()
    if text not in {"VERIFIED", "COMPUTED", "ESTIMATED", "INFERRED", "UNKNOWN"}:
        return "INFERRED"
    return text


def parse_json_content(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise SchemaError("model output was not JSON") from None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise SchemaError("model output was not JSON") from exc
    if not isinstance(value, dict):
        raise SchemaError("model output was not a JSON object")
    return value


class FakeNemotronClient:
    """Deterministic stand-in. Used by tests, CI, and sandbox demo."""

    model = "fake-nemotron"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, purpose: str, context: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
        self.calls += 1
        if purpose == "analyze_plan":
            payload = _fake_plan(context)
        elif purpose == "propose_repairs":
            payload = _fake_repairs(context)
        else:
            raise SchemaError(f"unknown purpose {purpose}")
        return schema.model_validate(payload)


def _fake_plan(context: dict[str, Any]) -> dict[str, Any]:
    constraints = context.get("constraints") or []
    hard = [
        {
            "id": item["id"],
            "description": item["description"],
            "hardness": "hard",
            "epistemic_status": "VERIFIED",
        }
        for item in constraints
        if item.get("hardness") == "hard"
    ]
    unknowns = list(context.get("unknowns") or [])
    return {
        "goals": [{"id": "g1", "description": context.get("plan") or "Satisfy the requested plan."}],
        "hard_constraints": hard,
        "soft_preferences": [],
        "dependencies": [
            {
                "id": "dep-inferred",
                "source": "plan",
                "target": hard[0]["id"] if hard else "goal",
                "relation": "DEPENDS_ON",
                "rationale": "The request depends on the declared hard constraints.",
                "epistemic_status": "INFERRED",
            }
        ],
        "uncertain_variables": [
            {
                "id": item,
                "description": f"{item} is unresolved",
                "why_material": "Changing it could change feasibility.",
            }
            for item in unknowns
        ],
        "unknowns": unknowns,
        "hazards": [
            {
                "id": "h1",
                "description": "A nominally feasible option may still fail under a small exogenous perturbation.",
                "related_variables": [],
            }
        ],
        "intended_bundle_id": None,
    }


def _fake_repairs(context: dict[str, Any]) -> dict[str, Any]:
    repairs = []
    for bundle in (context.get("bundles") or [])[:5]:
        repairs.append(
            {
                "id": bundle["id"],
                "label": bundle["label"],
                "action_ids": bundle["action_ids"],
                "rationale": bundle.get("rationale") or "Catalog option.",
            }
        )
    return {"repairs": repairs}


class NebiusClient:
    def __init__(self, ledger: BudgetLedger, cache: ResponseCache) -> None:
        self.ledger = ledger
        self.cache = cache
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, purpose: str, context: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
        if os.environ.get("NEBIUS_LIVE") != "1":
            raise LiveDisabled("NEBIUS_LIVE is not 1. Refusing to call Token Factory.")
        model = os.environ.get("NEBIUS_MODEL") or DEFAULT_MODEL
        self._guard_model(model)
        if purpose not in PURPOSE_TOKENS:
            raise SchemaError(f"unknown purpose {purpose}")
        prompt_name, max_tokens = PURPOSE_TOKENS[purpose]
        version = prompt_hash(prompt_name)
        messages = [
            {"role": "system", "content": prompt_text(prompt_name)},
            {"role": "user", "content": json.dumps(context, sort_keys=True)},
        ]
        params = {"temperature": 0, "max_tokens": max_tokens, "enable_thinking": False}
        key = _messages_hash(model, messages, params, version)
        cached = self.cache.get(key)
        if cached is not None:
            self.calls.append({"purpose": purpose, "cache_hit": True, "cost_usd": 0, "model": model})
            return schema.model_validate(cached["parsed"])

        estimated_in = estimate_tokens(messages[0]["content"] + messages[1]["content"])
        worst = cost_usd(model, estimated_in, params["max_tokens"])
        reservation = self.ledger.reserve(worst, purpose)
        started = time.perf_counter()
        try:
            content, usage = self._http(model, messages, params["max_tokens"])
            actual = cost_usd(model, int(usage["prompt_tokens"]), int(usage["completion_tokens"]))
            self.ledger.reconcile(reservation, actual)
        except BudgetError:
            raise
        except Exception:
            self.ledger.release(reservation)
            raise
        try:
            parsed = coerce_payload(schema, parse_json_content(content))
            model_obj = schema.model_validate(parsed)
        except (SchemaError, ValidationError) as exc:
            detail = _schema_detail(exc)
            self.calls.append(
                {
                    "call_id": uuid.uuid4().hex,
                    "purpose": purpose,
                    "model": model,
                    "schema_valid": False,
                    "error": detail,
                    "cache_hit": False,
                    "latency_s": time.perf_counter() - started,
                }
            )
            raise SchemaError(detail) from exc
        self.cache.put(key, {"parsed": model_obj.model_dump(mode="json")})
        self.calls.append(
            {
                "call_id": uuid.uuid4().hex,
                "purpose": purpose,
                "model": model,
                "input_tokens": int(usage["prompt_tokens"]),
                "output_tokens": int(usage["completion_tokens"]),
                "estimated_cost_usd": worst,
                "actual_cost_usd": actual,
                "latency_s": time.perf_counter() - started,
                "cache_hit": False,
                "schema_valid": True,
                "prompt_hash": version,
            }
        )
        return model_obj

    def _guard_model(self, model: str) -> None:
        from shadow.llm.pricing import PRICES

        if model not in PRICES:
            raise LiveDisabled(f"unknown model {model}")
        lowered = model.lower()
        if "ultra" in lowered and os.environ.get("ALLOW_ULTRA", "false").lower() != "true":
            raise LiveDisabled("Ultra is disabled")
        if "super" in lowered and os.environ.get("ALLOW_SUPER", "false").lower() != "true":
            raise LiveDisabled("Super is disabled")

    def _http(self, model: str, messages: list[dict[str, str]], max_tokens: int) -> tuple[str, dict[str, int]]:
        key = os.environ.get("NEBIUS_API_KEY")
        if not key:
            raise LiveDisabled("NEBIUS_API_KEY is not set")
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=os.environ.get("NEBIUS_BASE_URL") or DEFAULT_BASE_URL)
        response = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        choice = response.choices[0].message
        content = choice.content or ""
        reasoning = getattr(choice, "reasoning", None)
        usage = response.usage
        details = getattr(usage, "completion_tokens_details", None) if usage else None
        reasoning_tokens = int(getattr(details, "reasoning_tokens", 0) or 0) if details else 0
        returned = str(getattr(response, "model", "") or "")
        if returned and model not in returned and returned not in model:
            raise LiveDisabled("response model did not match the request")
        if reasoning or reasoning_tokens or "<think" in content.lower():
            raise LiveDisabled("thinking was not disabled")
        return content, {
            "prompt_tokens": int(usage.prompt_tokens if usage else 0),
            "completion_tokens": int(usage.completion_tokens if usage else 0),
        }


def model_client(ledger: BudgetLedger, cache: ResponseCache):
    if os.environ.get("NEBIUS_LIVE") == "1":
        return NebiusClient(ledger, cache)
    return FakeNemotronClient()


__all__ = ["FakeNemotronClient", "NebiusClient", "PlanSpec", "RepairProposal", "model_client"]
