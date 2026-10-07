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
- Frozen compile route: compiler_verifier (Lightning proposal plus deterministic verifier). Super lost on the development set
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
1. Record the demo, including Future Lab and Shadow Watch
2. Cross-plan combined graph when two saved futures disagree
3. Leave live Calendar, Gmail, and Tavily off until credentials exist

## This pass
- Future Lab simulates material exogenous variables locally. Nearest failure reuses the stored search
- Life graph is projected from scenario facts. Links stay INFERRED
- Each analyzed plan is a Future. Status is FRAGILE when a failure was discovered
- Cross-plan conflict fires only when two futures set the same resource differently
- Outcome receipt reads the existing event ledger
- No new Nebius spend. Frozen benchmarks were not rerun

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
- recorded repo ledger: 0.02313168
- recorded known total: 0.04345980
- one pre-fix call was omitted from the ledger; usage was not stored
- model: nvidia/Nemotron-3_5-Lightning
- official pilot: live-pilot-20261007T180515Z
- overall cap 1.00, repo soft cap 0.25, this session cap 0.03
