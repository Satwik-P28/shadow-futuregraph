# Architecture

Shadow separates semantic proposals from computation, and semantic authority from system authority.

```mermaid
flowchart LR
  plan[Plan] --> retrieve[Retrieval]
  retrieve --> nemotron[Nemotron structure and repair ids]
  nemotron --> graph[Future graph]
  graph --> search[Failure search]
  search --> repair[Repair evaluator]
  repair --> diff[Future diff]
  diff --> contract[Future contract]
  contract --> broker[Shadow broker]
  broker --> openshell[OpenShell boundary]
  openshell --> adapters[Sandbox or test adapters]
  adapters --> ledger[Event ledger]
  ledger --> reconcile[Reconcile]
```

## Nemotron

Two structured calls on a normal sandbox plan, both temperature 0, thinking disabled via `chat_template_kwargs.enable_thinking=false`, output cap 512 tokens. A live `compile_world` call, when `NEBIUS_LIVE=1`, uses the Super model selected in `shadowbench/compiler-study/decision.json`. Repair and plan calls stay on Lightning. The audit merge does not run by default.

1. `analyze_plan` returns goals, constraints, inferred dependencies, unknowns, and hazard hypotheses.
2. `propose_repairs` returns at most five repairs whose action ids must already exist.

Malformed JSON gets one local extraction attempt, then the call fails closed. There is no agent loop.

## Deterministic core

Typed expressions. No `eval` of model text.

- Constraints are temporal, numeric, equality, boolean, resource, or sequence records.
- Simulation samples exogenous numeric ranges with Sobol, then refines along axes and pairs. Cap 1024 evaluations per repair.
- Failure radius is the smallest normalized L2 perturbation the search found. The label is "nearest discovered failure".
- A minimal set still fails, and stops failing when any one member is removed. Sets of size at most 8 are checked exactly.
- Ranking is lexicographic: hard violations, unresolved hard constraints, failure radius, number of changes, cost, reversibility. The model does not score this.
- Z3 runs only on purely linear numeric scenarios. Anything else is reported as `unsupported`, which is not a proof.

## Tavily

Optional live search for disruptions and other external facts that can invalidate an assumption. Each stored fact keeps the query, source, timestamp, claim, and provenance. Without `TAVILY_API_KEY`, the sandbox search provider is used and the UI says `SANDBOX`.

## Shadow broker

`authorize(contract, action, world)` checks action type, resource, cost, spending limit, expiry status, and whether the contract is still active. A Google Calendar scope would not be sufficient to move an event the contract does not name.

## OpenShell

The compiler emits filesystem, process, and network rules. An operator boundary in `openshell/boundary.yaml` is the maximum. If `openshell-prover` is absent, the status is `prover_unavailable` and the UI must not say formally verified. OpenShell does not prove "only this calendar event".

## Adapters

`preview`, `execute`, `verify`, `compensate`. The sandbox travel and calendar providers back the demo. Duffel runs only with a `duffel_test_` token and refuses `live_mode`. Google Calendar writes also require `SHADOW_REAL_ACTIONS_ENABLED=true`.

## Event store

Append-only SQLAlchemy rows: event id, plan id, timestamp, type, redacted payload, payload hash, provenance. Local provider state can be replayed from `ACTION_EXECUTED` and `COMPENSATION_EXECUTED`.

## What the model is not allowed to do

Arithmetic, time math, graph traversal, simulation, constraint propagation, cut-set minimization, ranking, token accounting, or emitting executable code.
