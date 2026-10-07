"""Reserve worst-case cost before a call and reconcile to actual usage."""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

OVERALL_CAP_USD = 1.00
PRIOR_EXTERNAL_SPEND_USD = 0.02030592
REPO_SOFT_CAP_USD = 0.25


class BudgetError(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._fresh())

    def _fresh(self) -> dict[str, Any]:
        return {
            "overall_cap_usd": OVERALL_CAP_USD,
            "prior_external_spend_usd": PRIOR_EXTERNAL_SPEND_USD,
            "repo_soft_cap_usd": REPO_SOFT_CAP_USD,
            "repo_actual_spend_usd": 0.0,
            "committed_usd": 0.0,
            "reservations": {},
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def remaining_repo(self, data: dict[str, Any] | None = None) -> float:
        data = data if data is not None else self.snapshot()
        remaining = (
            float(data["repo_soft_cap_usd"])
            - float(data["repo_actual_spend_usd"])
            - float(data["committed_usd"])
        )
        if remaining < -1e-9:
            raise BudgetError("negative remaining budget")
        return round(remaining, 10)

    def remaining_overall(self, data: dict[str, Any] | None = None) -> float:
        data = data if data is not None else self.snapshot()
        remaining = (
            float(data["overall_cap_usd"])
            - float(data["prior_external_spend_usd"])
            - float(data["repo_actual_spend_usd"])
            - float(data["committed_usd"])
        )
        if remaining < -1e-9:
            raise BudgetError("negative remaining budget")
        return round(remaining, 10)

    def reserve(self, worst_case_usd: float, purpose: str) -> str:
        if worst_case_usd < 0:
            raise BudgetError("negative reservation")
        with self._lock:
            data = self._read()
            if worst_case_usd > self.remaining_repo(data) + 1e-12:
                raise BudgetError("repo soft cap would be exceeded")
            if worst_case_usd > self.remaining_overall(data) + 1e-12:
                raise BudgetError("overall cap would be exceeded")
            reservation_id = uuid.uuid4().hex
            data["committed_usd"] = round(float(data["committed_usd"]) + worst_case_usd, 10)
            data["reservations"][reservation_id] = {
                "worst_case_usd": worst_case_usd,
                "purpose": purpose,
                "open": True,
            }
            self._write(data)
            return reservation_id

    def release(self, reservation_id: str) -> None:
        with self._lock:
            data = self._read()
            item = data["reservations"].get(reservation_id)
            if not item or not item["open"]:
                raise BudgetError("reservation is not open")
            item["open"] = False
            item["actual_usd"] = 0.0
            data["committed_usd"] = round(float(data["committed_usd"]) - float(item["worst_case_usd"]), 10)
            self._write(data)

    def reconcile(self, reservation_id: str, actual_usd: float) -> dict[str, Any]:
        if actual_usd < 0:
            raise BudgetError("negative actual cost")
        with self._lock:
            data = self._read()
            item = data["reservations"].get(reservation_id)
            if not item or not item["open"]:
                raise BudgetError("reservation is not open")
            if actual_usd - float(item["worst_case_usd"]) > 1e-9:
                raise BudgetError("actual cost exceeds reservation")
            item["open"] = False
            item["actual_usd"] = actual_usd
            data["committed_usd"] = round(float(data["committed_usd"]) - float(item["worst_case_usd"]), 10)
            data["repo_actual_spend_usd"] = round(float(data["repo_actual_spend_usd"]) + actual_usd, 10)
            self._write(data)
            return data

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text())

    def _write(self, data: dict[str, Any]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, self.path)
