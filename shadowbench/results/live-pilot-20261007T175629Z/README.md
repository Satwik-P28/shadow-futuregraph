# Live Nemotron pilot

propose_repairs was capped at 256 tokens and returned truncated JSON. The later rerun raises that cap to 512. Shadow's 30/30 here still scored the typed catalog when parsing failed.

This is a live Lightning pilot, not the local scripted gate.

- Run: `live-pilot-20261007T175629Z`
- Model: `nvidia/Nemotron-3_5-Lightning`
- Temperature 0, thinking disabled, Super off, Ultra off
- Frozen worlds: 30 completed of 30
- New validation spend USD: 0.00849066
- Total known spend USD: 0.02881878
- Stopped early: False
- Context reduced after world: None
- Prompts were frozen before the pilot. No prompt was edited after seeing these outputs.
- Direct, planner, and critic see the shared pilot context only.
- Shadow also uses formulas, bounds, and effects inside the deterministic engine.
- The oracle is stored in `oracle.json` and is not sent to the model.
- Hero schema valid: False. Recommended: None.
- Tavily: skipped.
- OpenShell: prover_unavailable.

Sample size 30 is a pilot. Intervals are bootstrap estimates, not a conclusive ranking.
