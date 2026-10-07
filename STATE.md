# STATE

## Phase
P0 depth. https://github.com/Satwik-P28/shadow-futuregraph (main)

## Completed
- Hero loop on synthetic Alex data: graph, minimal failure, repair, diff, contract, broker, sandbox execute, inject
- Apartment scenario on the same engine
- Impossible plan returns NO_FEASIBLE_FUTURE. Unknown venue stays unknown until an event resolves it
- Budget ledger, cache, FakeNemotron, live client
- ShadowBench local-gate, 30 monotone worlds, $0, scripted stand-in
- Live Lightning pilot, 30 heterogeneous worlds, recorded spend $0.01838022
- Frontend production build, Vitest, Playwright hero
- OpenShell compiler. Prover not installed
- Public repo, secret scan clean, Apache-2.0

## Architecture decisions
- Domain data is JSON. Search, repair, broker do not branch on scenario id
- Naive plan = lowest sticker cost among nominally feasible bundles
- Recommendation = violations, unresolved, failure radius, changes, cost, reversibility
- Nemotron proposes. It does not rank or authorize
- Model `nvidia/Nemotron-3_5-Lightning`. Ultra off
- Earlier frozen route remains `shadowbench/routing/decision.json`: compiler_verifier
- New compiler study `shadowbench/compiler-study/` selected Super for live `compile_world` only. Ordinary calls stay on Lightning. Ultra off. The audit did not improve the measured rates, so it is not the default path
- Shadow Watch reacts to world events. Three typed skills do not grant authority. Approved contracts persist in the event database
- Prices only in `backend/shadow/llm/pricing.py`, checked_at 2026-10-07

## Important paths
- `fixtures/travel/world.json`
- `fixtures/apartment/world.json`
- `backend/shadow/failures/search.py`
- `backend/shadow/repair/evaluate.py`
- `backend/shadow/runtime/broker.py`
- `backend/shadow/llm/client.py`
- `backend/shadow/pipeline.py`
- `frontend/src/App.tsx`
- `shadowbench/results/local-gate/summary.json`
- `shadowbench/results/live-pilot-20261007T180515Z/summary.json`

## Known failures
- `openshell-prover` is not on PATH. Status is `prover_unavailable`
- Duffel, Google Calendar, and Tavily are implemented and unconfigured
- Public demo: https://shadow-futuregraph.onrender.com (Render, sandbox, no API key)
- Demo video not recorded
- World Compiler holdout: HardConstraintRecall 5/10, FalseHardConstraintRate 0/8, MaterialDependencyRecall 1/2, FalseDependencyRate 0/1, UnknownPreservationRate 1/2, ProvenanceCoverage 21/21, EndToEndRepairSuccess 10/16
- Adversarial holdout: Shadow 9/10, no-search 7/10, failure recall 6/6, false hazards 0/10, regret 0.1. Miss: non_monotonic selected the larger-radius repair

## Next 3 tasks
1. Confirm the red-team commit on the public sandbox, including two-browser isolation
2. Leave live Calendar, Gmail, and Tavily off until credentials exist
3. Do not rerun the frozen 30-world pilot, compiler study, or red-team live pass

## This pass
- Cross-plan conflicts now cover value, time overlap, explicit shared budget, protected resources, and asset state
- The sandbox home shows Alex's airport window against a protected gallery opening
- Reset demo restores that pair and clears in-memory plans and approved contracts
- Compiler study: 32 development cases, 24 frozen test cases, four architectures. Super won. Test hard recall 10/13, false hard 0/18, repair 19/24
- Live compile uses Super only when NEBIUS_LIVE=1. The public demo stays deterministic
- Calendar, Gmail, and Tavily are not configured
- New Nebius spend this pass: 0.01129200

## Red team
- Public demo sessions are isolated by an HttpOnly cookie. Reset clears only that browser
- The hero phrase table moved to `example_world.py`. Generic `compile_bundle` does not license fixture ids
- Attack set `shadowbench/redteam-compiler/`: rules-only hard recall 0/25, example adapter 0/25, Super plus verifier 18/25, false hard 0, dependencies 3/6, unknowns 3/8, contradictions 0/2, repair proxy 28/40
- Fair raw-context search benchmark was not built. The compiler emits labels, not executable formulas
- Unknown events no longer mark unrelated futures unknown. Unmatched skills return none
- New Nebius spend this red-team pass: 0.00678450
- recorded repo ledger: 0.04120818
- recorded known total: 0.06153630

## Test commands
- `make test`
- `make benchmark-local`
- `cd frontend && npm run build`

## Live-token spend
- live pilot ledger portion: 0.01838022
- earlier repo call, not in this ledger: 0.0000222
- prior external: 0.02030592
- recorded known total before this pass: 0.03870834
- World Compiler holdout, 16 Lightning calls: 0.00059778
- recorded known total before the route study: 0.03930612
- route study, development plus one holdout: 0.00415368
- recorded repo ledger before this pass: 0.02313168
- recorded known total before this pass: 0.04345980
- compiler study this pass, probe plus development plus one test: 0.01129200
- recorded repo ledger: 0.03442368
- recorded known total: 0.05475180
- one pre-fix call was omitted from the ledger; usage was not stored
- model: nvidia/Nemotron-3_5-Lightning
- official pilot: live-pilot-20261007T180515Z
- overall cap 1.00, repo soft cap 0.25, this session cap 0.03
