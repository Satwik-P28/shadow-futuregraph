# STATE

## Phase
Published. https://github.com/Satwik-P28/shadow-futuregraph (main)

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
- Model `nvidia/Nemotron-3_5-Lightning`. Super and Ultra off
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
- No hosted deploy
- Demo video not recorded

## Next 3 tasks
1. Record the demo video outside this build
2. Submit the Devpost form and judge feedback
3. Optional: install openshell-prover, or host the Docker image

## Test commands
- `make test`
- `make benchmark-local`
- `cd frontend && npm run build`

## Live-token spend
- recorded repo ledger: 0.01838022
- earlier repo call, not in this ledger: 0.0000222
- prior external: 0.02030592
- recorded known total: 0.03870834
- one pre-fix call was omitted from the ledger; usage was not stored
- model: nvidia/Nemotron-3_5-Lightning
- official pilot: live-pilot-20261007T180515Z
- overall cap 1.00, repo soft cap 0.25, this session cap 0.03
