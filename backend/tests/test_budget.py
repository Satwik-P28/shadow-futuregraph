import threading
from pathlib import Path

import pytest

from shadow.llm.budget import PRIOR_EXTERNAL_SPEND_USD, BudgetError, BudgetLedger
from shadow.llm.client import NebiusClient, ResponseCache, parse_json_content
from shadow.llm.pricing import CHECKED_AT, cost_usd


def test_prices_and_reconciliation(tmp_path: Path):
    assert CHECKED_AT == "2026-10-07"
    ledger = BudgetLedger(tmp_path / "budget.json")
    snap = ledger.snapshot()
    assert snap["overall_cap_usd"] == 1.0
    assert snap["prior_external_spend_usd"] == PRIOR_EXTERNAL_SPEND_USD
    assert snap["repo_soft_cap_usd"] == 0.25
    reservation = ledger.reserve(0.01, "smoke")
    data = ledger.reconcile(reservation, 0.004)
    assert data["repo_actual_spend_usd"] == 0.004
    assert ledger.remaining_repo() > 0
    assert cost_usd("nvidia/Nemotron-3_5-Lightning", 1_000_000, 0) == 0.06


def test_failed_reservation_releases(tmp_path: Path):
    ledger = BudgetLedger(tmp_path / "budget.json")
    reservation = ledger.reserve(0.02, "call")
    ledger.release(reservation)
    assert ledger.snapshot()["committed_usd"] == 0
    assert ledger.snapshot()["repo_actual_spend_usd"] == 0


def test_cap_blocks_before_work(tmp_path: Path):
    ledger = BudgetLedger(tmp_path / "budget.json")
    with pytest.raises(BudgetError):
        ledger.reserve(0.30, "too big")
    assert ledger.snapshot()["committed_usd"] == 0


def test_concurrent_reservations_cannot_exceed_cap(tmp_path: Path):
    ledger = BudgetLedger(tmp_path / "budget.json")
    ok: list[str] = []
    failed = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal failed
        try:
            ok.append(ledger.reserve(0.10, "parallel"))
        except BudgetError:
            with lock:
                failed += 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(ok) <= 2
    assert ledger.snapshot()["committed_usd"] <= 0.25 + 1e-9
    assert ledger.remaining_repo() >= 0


def test_cache_hit_costs_zero_and_breach_skips_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from shadow.core.models import PlanSpec
    from shadow.llm.client import _fake_plan

    monkeypatch.setenv("NEBIUS_LIVE", "1")
    monkeypatch.setenv("NEBIUS_API_KEY", "not-a-real-key")
    ledger = BudgetLedger(tmp_path / "budget.json")
    cache = ResponseCache(tmp_path / "cache.sqlite")
    client = NebiusClient(ledger, cache)
    context = {"plan": "move", "constraints": [], "unknowns": [], "bundles": []}
    calls = {"n": 0}

    def fake_http(model: str, messages: list[dict[str, str]], max_tokens: int) -> tuple[str, dict[str, int]]:
        del model, messages, max_tokens
        calls["n"] += 1
        return __import__("json").dumps(_fake_plan(context)), {"prompt_tokens": 20, "completion_tokens": 8}

    client._http = fake_http  # type: ignore[method-assign]
    client.complete_json("analyze_plan", context, PlanSpec)
    spent = ledger.snapshot()["repo_actual_spend_usd"]
    client.complete_json("analyze_plan", context, PlanSpec)
    assert calls["n"] == 1
    assert ledger.snapshot()["repo_actual_spend_usd"] == spent
    blocker = BudgetLedger(tmp_path / "full.json")
    blocker.reserve(0.25, "fill")
    blocked = NebiusClient(blocker, ResponseCache(tmp_path / "cache2.sqlite"))

    def explode(model: str, messages: list[dict[str, str]], max_tokens: int) -> tuple[str, dict[str, int]]:
        del model, messages, max_tokens
        raise AssertionError("http should not run")

    blocked._http = explode  # type: ignore[method-assign]
    with pytest.raises(BudgetError):
        blocked.complete_json("analyze_plan", context, PlanSpec)
    parsed = parse_json_content("```json\n{\"repairs\": []}\n```")
    assert parsed == {"repairs": []}
