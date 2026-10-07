# Live Nemotron pilot

This is a live Lightning pilot, not the local scripted gate.

- Run: `live-pilot-20261007T180515Z`
- Model: `nvidia/Nemotron-3_5-Lightning`
- Temperature 0, thinking disabled, Super off, Ultra off
- Frozen worlds: 30 completed of 30
- New validation spend USD: 0.01838022
- Total known spend USD: 0.03870834
- Stopped early: False
- Context reduced after world: None
- Prompt text was not edited after the first pilot.
- propose_repairs max_tokens was raised from 256 to 512 after the first pilot truncated JSON at 256 tokens.
- Choice and analyze calls from the first pilot are cache hits on this rerun.
- Direct, planner, and critic see the shared pilot context only.
- Shadow also uses formulas, bounds, and effects inside the deterministic engine.
- The oracle is stored in `oracle.json` and is not sent to the model.
- Hero schema valid: True. Recommended: b1120.
- Tavily: skipped.
- OpenShell: prover_unavailable.

Sample size 30 is a pilot. Intervals are bootstrap estimates, not a conclusive ranking.

| System | Task completion | Undetected failures | Failure recall | Repair success | Mean regret |
| --- | --- | --- | --- | --- | --- |
| direct_nemotron | 6/30 | 22/26 | 9/30 | 6/30 | 0.800 |
| planner | 8/30 | 22/26 | 8/30 | 8/30 | 0.733 |
| planner_critic | 5/30 | 8/26 | 22/30 | 5/30 | 0.833 |
| shadow_no_failure_search | 8/30 | 22/26 | 8/30 | 8/30 | 0.733 |
| shadow | 30/30 | 0/26 | 30/30 | 30/30 | 0.000 |

Shadow cut precision/recall were 1.0 where the nominal plan was unsafe. Planner-critic recall is higher than its task completion. The no-search ablation matches the planner. Context was not shortened on this run.
