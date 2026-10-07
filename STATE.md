# STATE

## Phase
Published. https://github.com/Satwik-P28/shadow-futuregraph @ 11364a9fd09ab2277e6e0827c2bb612785a5bb01

## Completed
- Hero loop on synthetic Alex data: graph, minimal failure, repair, diff, contract, broker, sandbox execute, inject
- Apartment scenario on the same engine
- Impossible plan returns NO_FEASIBLE_FUTURE. Unknown venue stays unknown until an event resolves it
- Budget ledger, cache, FakeNemotron, live client
- ShadowBench local-gate, 30 worlds, $0, Full Shadow 30/30 vs baselines 0/30
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
- repo_actual_spend_usd: 0.0000222
- paid calls this build: 1
- model: nvidia/Nemotron-3_5-Lightning
- usage: 134 input, 59 output, schema valid
- overall cap 1.00, prior external 0.02030592, repo soft cap 0.25
