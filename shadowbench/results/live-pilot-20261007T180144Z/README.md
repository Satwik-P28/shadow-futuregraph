# Live Nemotron pilot

This rerun shortened the context after world 5 because the cost gate counted earlier session spend. Do not use it as the comparison. See the later unshrunk rerun.

This is a live Lightning pilot, not the local scripted gate.

- Run: `live-pilot-20261007T180144Z`
- Model: `nvidia/Nemotron-3_5-Lightning`
- Temperature 0, thinking disabled, Super off, Ultra off
- Frozen worlds: 30 completed of 30
- New validation spend USD: 0.01602792
- Total known spend USD: 0.03635604
- Stopped early: False
- Context reduced after world: 5
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
