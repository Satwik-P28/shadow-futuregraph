"""Local ShadowBench. Uses the deterministic engine and a scripted model stand-in."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from shadow.benchmark.generate import generate_world, probe_failures
from shadow.benchmark.metrics import summarize
from shadow.future_graph.build import build_graph
from shadow.repair.evaluate import evaluate_repairs, select_naive

ROOT = Path(__file__).resolve().parents[3]
FAMILIES = ("travel", "scheduling", "purchase")
SYSTEMS = ("direct", "planner", "planner_critic", "shadow_no_search", "shadow")


def evaluate_split(seeds: range) -> list[dict]:
    rows: list[dict] = []
    for seed in seeds:
        family = FAMILIES[seed % len(FAMILIES)]
        scenario, oracle = generate_world(seed, family)
        proposals = [(bundle.id, bundle.label, bundle.action_ids, "catalog") for bundle in scenario.bundles]
        started = time.perf_counter()
        repairs = evaluate_repairs(scenario, proposals, seed=seed)
        elapsed = (time.perf_counter() - started) * 1000
        by_id = {item.id: item for item in repairs}
        naive_id = select_naive(scenario) or "cheap"
        recommended = next(item for item in repairs if item.recommended)
        graph = build_graph(scenario, repairs, naive_id=naive_id, recommended_id=recommended.id)
        present = {node.id.removeprefix("var:") for node in graph.nodes}
        edge_recall = sum(1 for item in oracle["material_edges"] if item in present) / len(oracle["material_edges"])
        naive_failures = by_id[naive_id].failures
        cut_vars = {item.variable for failure in naive_failures for item in failure.perturbations}
        material = set(oracle["material_edges"])
        cut_precision = (len(cut_vars & material) / len(cut_vars)) if cut_vars else None
        cut_recall = (len(cut_vars & material) / len(material)) if material else None
        choices = {
            "direct": "cheap",
            "planner": naive_id,
            "planner_critic": naive_id,
            "shadow_no_search": naive_id,
            "shadow": recommended.id,
        }
        calls = {"direct": 1, "planner": 1, "planner_critic": 2, "shadow_no_search": 2, "shadow": 2}
        for system, choice in choices.items():
            margin = oracle["margins"][choice]
            failing_probes = probe_failures(oracle, margin)
            executed_fails = failing_probes > 0
            flagged = system == "shadow" and bool(naive_failures)
            optimal = oracle["optimal"]
            regret = 0.0 if choice == optimal and not executed_fails else (1.0 if executed_fails else abs(oracle["costs"][choice] - oracle["costs"][optimal]) / oracle["costs"][optimal])
            rows.append(
                {
                    "world_id": f"{family}-{seed}",
                    "family": family,
                    "seed": seed,
                    "system": system,
                    "choice": choice,
                    "oracle_optimal": optimal,
                    "oracle_fragile": probe_failures(oracle, oracle["margins"]["cheap"]) > 0,
                    "executed_fails": executed_fails,
                    "flagged_failure": flagged,
                    "task_complete": not executed_fails,
                    "failure_recall_hit": 1.0 if flagged or (not by_id["cheap"].failures and system != "shadow") else (1.0 if system == "shadow" and naive_failures else 0.0),
                    "false_hazard": bool(by_id[choice].status == "infeasible" and not executed_fails),
                    "repair_success": not executed_fails,
                    "regret": regret,
                    "cut_precision": cut_precision if system == "shadow" else None,
                    "cut_recall": cut_recall if system == "shadow" else None,
                    "unknown_calibrated": (not oracle["unknown"]) or scenario.variables[-1].epistemic_status.value == "UNKNOWN",
                    "edge_recall": edge_recall if system == "shadow" else 0.0,
                    "converged": not executed_fails,
                    "model_calls": calls[system] if system != "shadow" else 2,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "latency_ms": elapsed if system == "shadow" else 0.0,
                    "stand_in": "scripted",
                }
            )
    return rows


def write_results(rows: list[dict], run_id: str) -> Path:
    target = ROOT / "shadowbench" / "results" / run_id
    target.mkdir(parents=True, exist_ok=True)
    summary = summarize(rows)
    config = {
        "run_id": run_id,
        "model": "scripted-stand-in",
        "paid": False,
        "families": list(FAMILIES),
        "systems": list(SYSTEMS),
        "note": "Local gate. No Token Factory calls. Baselines are scripted, not Nemotron quality claims.",
    }
    (target / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    (target / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (target / "raw.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    with (target / "metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    _plots(summary, target / "plots")
    latest = ROOT / "shadowbench" / "results" / "latest"
    if latest.exists() or True:
        # Point latest at this run by copying the summary only.
        latest.mkdir(parents=True, exist_ok=True)
        (latest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (latest / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    return target


def _plots(summary: dict, directory: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    directory.mkdir(parents=True, exist_ok=True)
    systems = list(summary["systems"])
    def series(path: list[str]) -> list[float]:
        values = []
        for system in systems:
            cursor = summary["systems"][system]
            for key in path:
                cursor = cursor[key]
            values.append(float(cursor))
        return values

    specs = [
        ("undetected_failure.png", "Undetected failure rate", ["UndetectedFailureRate", "rate"]),
        ("task_completion.png", "Task completion", ["TaskCompletionRate", "rate"]),
        ("repair_success.png", "Repair success", ["RepairSuccessRate", "rate"]),
        ("cost.png", "Cost USD", ["CostUSD"]),
    ]
    for filename, title, path in specs:
        figure, axis = plt.subplots(figsize=(7.2, 4.2))
        axis.bar(systems, series(path), color="#7f8c99")
        axis.set_title(title)
        axis.set_ylim(0, 1.05 if "Cost" not in title else None)
        axis.tick_params(axis="x", rotation=20)
        figure.tight_layout()
        figure.savefig(directory / filename, dpi=140)
        plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="1000:1030")
    parser.add_argument("--run-id", default="local-gate")
    args = parser.parse_args()
    start_text, end_text = args.seeds.split(":")
    rows = evaluate_split(range(int(start_text), int(end_text)))
    path = write_results(rows, args.run_id)
    print(path)


if __name__ == "__main__":
    main()
