"""Score the primitive compiler on a frozen grammar holdout. No model calls in score mode.

The sentences are generated from the same forms the compiler documents. This is not
an open-world language test. Messy rows are included so a perfect score is not guaranteed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

OUT = ROOT / "shadowbench" / "primitive-holdout"
ORIGINS = ["harbor desk", "pottery studio", "loading dock", "choir room", "ticket booth"]
MIDS = ["badge queue", "coat check", "service alley", "side gate", "parcel cage"]
DESTS = ["clinic intake", "notary desk", "gallery talk", "vet window", "archive desk"]
BUYS = [("field recorder", 180), ("spare battery", 90), ("linen roll", 240), ("ink set", 70)]


def _clock(minutes: int) -> str:
    hour = minutes // 60
    suffix = "AM" if hour < 12 else "PM"
    show = hour % 12 or 12
    return f"{show}:{minutes % 60:02d} {suffix}"


def _case(index: int, split: str) -> dict:
    kind = index % 5
    origin = ORIGINS[index % len(ORIGINS)]
    mid = MIDS[index % len(MIDS)]
    dest = DESTS[index % len(DESTS)]
    end = 8 * 60 + (index % 4) * 30
    start = end + 70
    low_a, high_a = 15 + (index % 3) * 5, 35 + (index % 3) * 5
    low_b, high_b = 10, 25
    if kind == 0:
        records = [
            {"id": "a", "text": f"{origin.title()} ends at {_clock(end)}.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "b", "text": f"{origin.title()} to {mid} takes {low_a}-{high_a} minutes.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "c", "text": f"{mid.title()} to {dest} takes {low_b}-{high_b} minutes.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "d", "text": f"{dest.title()} starts at {_clock(start)} and cannot move.", "observed_at": "2026-10-01T00:00:00Z"},
        ]
        low = end + low_a + low_b <= start
        high = end + high_a + high_b <= start
        oracle = {"status": "READY", "low_feasible": low, "high_feasible": high}
    elif kind == 1:
        records = [
            {"id": "a", "text": f"{origin.title()} arrives at {_clock(end)}.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "b", "text": f"{dest.title()} starts at {_clock(start)} and cannot move.", "observed_at": "2026-10-01T00:00:00Z"},
        ]
        oracle = {"status": "NEEDS_INFORMATION"}
    elif kind == 2:
        records = [
            {"id": "a", "text": f"{dest.title()} starts at {_clock(start)}.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "b", "text": f"{dest.title()} starts at {_clock(start + 60)}.", "observed_at": "2026-10-02T00:00:00Z"},
        ]
        oracle = {"status": "CONTRADICTORY"}
    elif kind == 3:
        left, right = BUYS[index % len(BUYS)], BUYS[(index + 1) % len(BUYS)]
        cap = 200
        records = [
            {"id": "a", "text": f"{left[0].title()} costs ${left[1]}.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "b", "text": f"{right[0].title()} costs ${right[1]}.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "c", "text": f"Available budget is at most ${cap}.", "observed_at": "2026-10-01T00:00:00Z"},
        ]
        oracle = {"status": "READY", "over_budget": left[1] + right[1] > cap}
    else:
        records = [{"id": "a", "text": "Maybe we can sort of get there before the thing.", "observed_at": "2026-10-01T00:00:00Z"}]
        oracle = {"status": "UNSUPPORTED"}
    return {
        "id": f"{split}-{index:02d}",
        "plan": "Can I arrive in time?" if kind != 3 else "Can I buy both?",
        "records": records,
        "oracle": oracle,
    }


def _write(split: str, count: int) -> None:
    rows = [_case(index, split) for index in range(count)]
    path = OUT / split
    path.mkdir(parents=True, exist_ok=True)
    (path / "cases.json").write_text(json.dumps([{k: v for k, v in row.items() if k != "oracle"} for row in rows], indent=2) + "\n")
    (path / "oracle.json").write_text(json.dumps({row["id"]: row["oracle"] for row in rows}, indent=2) + "\n")


def _freeze() -> None:
    blob = b"".join((OUT / split / name).read_bytes() for split in ("dev", "test") for name in ("cases.json", "oracle.json"))
    digest = hashlib.sha256(blob).hexdigest()
    frozen = OUT / "FROZEN.sha256"
    if frozen.exists() and frozen.read_text().strip() != digest:
        raise SystemExit("primitive holdout changed after it was frozen")
    if not frozen.exists():
        frozen.write_text(digest + "\n")


def _score(split: str) -> dict:
    from shadow.simulation.engine import bind, evaluate_constraints
    from shadow.world.executable import compile_primitives

    cases = json.loads((OUT / split / "cases.json").read_text())
    oracle = json.loads((OUT / split / "oracle.json").read_text())
    status_hit = 0
    executable = 0
    low_hit = 0
    low_total = 0
    high_hit = 0
    high_total = 0
    for case in cases:
        compiled = compile_primitives(case["plan"], case["records"])
        expected = oracle[case["id"]]
        status_hit += compiled.status == expected["status"]
        if compiled.status == "READY" and compiled.scenario is not None:
            executable += 1
        if "low_feasible" in expected and compiled.scenario is not None:
            low_total += 1
            high_total += 1
            env = bind(compiled.scenario, {}, {})
            high = {
                var.id: float(var.upper)
                for var in compiled.scenario.variables
                if var.role == "exogenous" and var.upper is not None
            }
            hard = [item for item in compiled.scenario.constraints if item.hardness == "hard"]
            low_ok = all(evaluate_constraints(compiled.scenario, env)[item.id] is True for item in hard)
            high_env = bind(compiled.scenario, {}, high)
            high_ok = all(evaluate_constraints(compiled.scenario, high_env)[item.id] is True for item in hard)
            low_hit += low_ok is expected["low_feasible"]
            high_hit += high_ok is expected["high_feasible"]
    return {
        "cases": len(cases),
        "status_hit": status_hit,
        "executable_ready": executable,
        "low_hit": low_hit,
        "low_total": low_total,
        "high_hit": high_hit,
        "high_total": high_total,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not (OUT / "dev" / "cases.json").exists():
        _write("dev", 40)
        _write("test", 40)
    _freeze()
    payload = {"dev": _score("dev"), "test": _score("test"), "note": "grammar holdout, not open-world NLP, no model"}
    (OUT / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
