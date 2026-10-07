# Shadow

**Find bugs in your future before you commit to it.**

Public demo: https://shadow-futuregraph.onrender.com

No login and no API key. The badge stays SANDBOX. Demo video: not recorded. Script: `docs/DEMO_SCRIPT.md` (2:40–2:55).

Shadow compiles messy personal context into a typed model of the future around a plan, searches that model for nearby failures, repairs the plan, asks you to approve the repaired future, executes only those state transitions, and checks the result.

1. Messy personal context: calendar, email, reservations, and preferences.
2. World Compiler: candidate goals, constraints, dependencies, and unknowns, each with provenance.
3. Future Graph: the typed world the deterministic engine actually searches.
4. Failure search: the nearest modeled way the nominal plan breaks.
5. Repair: a counterfactual bundle the evaluator scores. The model does not score it.
6. Approval: a future contract, not a general tool grant.
7. Safe execution: sandbox actions inside that contract, then a reconciliation check.

## Why Shadow is Personal AI

The public demo keeps sandbox state for one browser session. It is not a private store on your device, and it is not connected to your calendar or mail. A live compile, which that demo does not make, would send the relevant record text to Nebius. You can hand the sandbox a plan. It builds a Future Graph, finds failures inside the example model, repairs the plan, and executes only the changes you approve.

After approval, Shadow Watch keeps that future. It does not poll every service. When a connected source emits a world event, Shadow looks up the contracts that depend on the changed fact, rechecks those constraints, and leaves the others alone. If the future still holds, authority stays. If it does not, the contract goes stale, authority is revoked, and a repair is proposed for approval. Shadow does not execute that repair on its own.

Three typed skills reuse the same engine: Reschedule Trip, Handle Trip Disruption, and Coordinate Schedule. A skill lists what it can read, change, verify, and compensate. It does not grant authority. The Future Contract does. The broker enforces that contract.

`GET /api/personal-ai/status` reports watched futures, memory counts, skills, connected tools, and the privacy mode. See `docs/PERSONAL_AI_TRACK.md`.

## Why Shadow

A planner that checks the happy path will book the cheaper flight that arrives at 17:05 and still miss a 19:00 dinner once a delay stacks with traffic. Shadow treats that as a bug in the future, not as a chat to continue. You approve the repaired future. The semantic broker will not move an unrelated calendar event just because a calendar API is available.

## 30-second example

Alex, a synthetic persona, asks: "Move my NYC trip to Friday and make sure everything still works."

The world has a 19:00 dinner that cannot move, a Friday design review that cannot move, an algorithms exam that must stay untouched, a $100 fare cap, and three Friday flights. The 14:40 flight is the cheapest one that still reaches dinner if nothing goes wrong. Search finds a nearer failure: a modest delay together with extra ground time. Neither piece alone, at that size, misses dinner. The 11:20 flight survives a much larger perturbation and costs $76 more. Moving dinner is proposed and rejected because dinner is a hard constraint. After approval, the sandbox updates the flight, the ride, and the trip event, then blocks an attempt to move the exam.

Nothing in the search source names "11:20". The fixture states the times, ranges, and constraints. The ranking is lexicographic over measured violations and failure radius.

## How it works

1. Retrieve material facts. Support, attack, and unresolved evidence. Not embedding search.
2. Nemotron, when live, proposes structure and at most five repairs. It does not rank them.
3. Build a typed future graph and prune it to what reaches a constraint or outcome.
4. Sample exogenous ranges, then refine near the boundary. Cap 1024 worlds per repair.
5. Reduce each discovered failure to a minimal perturbation set.
6. Re-simulate every repair. Recommend by hard violations, unresolved constraints, failure radius, change count, cost, then reversibility.
7. Show the future diff. Approval mints a contract.
8. The broker authorizes each action. Execution is idempotent, verified, and logged.
9. A later world change invalidates the affected assumption and revokes authority when an invariant breaks.

## Architecture

```mermaid
flowchart LR
  plan[Plan] --> nemotron[Nemotron proposals]
  nemotron --> graph[Future graph]
  graph --> search[Failure search]
  search --> repair[Repair evaluator]
  repair --> contract[Future contract]
  contract --> broker[Shadow broker]
  broker --> boundary[OpenShell boundary]
  boundary --> adapters[Sandbox or test adapters]
```

Detail is in `docs/ARCHITECTURE.md`.

| Piece | Role |
| --- | --- |
| Nemotron 3.5 Lightning on Nebius Token Factory | Semantic structure and repair proposals |
| Deterministic core | Constraints, simulation, minimal failures, ranking |
| Tavily | Live external evidence when a key is set |
| Shadow broker | Which resource the approved future may change |
| OpenShell | Filesystem, process, and network boundary when the prover is installed |
| Adapters | Sandbox by default. Duffel test mode and Google Calendar only with credentials |
| Event ledger | Append-only replay of what was authorized and verified |

## Future graph

Nodes are current state, actions, exogenous events, derived state, constraints, outcomes, failures, repairs, evidence, and unknowns. Edges are causes, constrains, depends-on, enables, precedes, violates, mitigates, supported-by, and invalidates. Interactive caps are about 80 nodes, 160 edges, and depth that stays on the material path. The default view hides detail nodes.

Epistemic status stays visible: verified, computed, estimated, inferred, unknown. Inferred edges are not promoted, and unknown variables are not given a probability.

## Minimal failure search

A perturbation is a change from the declared baseline. Continuous values are scaled by the variable's declared range. The radius is the smallest normalized L2 distance this search actually found. The UI calls it the nearest discovered failure.

For each failing point the search removes perturbations until removing any one of the rest stops the failure. Small sets are checked exactly. The afternoon flight's dinner failure is a two-variable set. The evening flight fails with the empty set: it is already late.

## Counterfactual repair

Every catalog repair and every model proposal is applied to a cloned world and searched again. A proposal that references an action id outside the catalog is dropped. A proposal that moves dinner fails the hard constraint and is not recommended.

## Outcome-scoped execution

The contract names the flight, the ride, and the trip event. `update_exam` is forbidden even though it is a calendar update of the same type. Idempotency keys are `contract_id:action_id`. A timeout after a commit reconciles the stored result instead of mutating twice. If the calendar step fails after the flight has committed, the flight is kept and the calendar step can be retried. Verification that does not match provider state does not claim success.

Injecting `+74` minutes updates the delay assumption. The early flight still makes dinner, so authority stays. Injecting `+$80` breaks the fare cap, marks the contract stale, and halts execution.

## NVIDIA / Nebius integration

One client, `backend/shadow/llm/client.py`.

- Base URL `https://api.tokenfactory.nebius.com/v1`
- Model `nvidia/Nemotron-3_5-Lightning`
- `temperature=0`
- `chat_template_kwargs.enable_thinking=false`
- `max_tokens=512`
- Prices in `backend/shadow/llm/pricing.py`, `checked_at=2026-10-07`
  - Lightning $0.06 / $0.24 per 1M input / output
  - Super $0.30 / $0.90
  - Ultra $1.00 / $3.00

`NEBIUS_LIVE` must be `1` or the client throws before the request. The ledger's repo soft cap is $0.25 on top of $0.02030592 historical spend, under a $1.00 overall cap. Reservations use a conservative token estimate and the full output cap. Actual usage reconciles the reservation. Cache hits cost $0. A breach never opens the socket.

Ultra stays off unless `ALLOW_ULTRA=true`. Super is not used for ordinary plan or repair calls. A later compiler study may call Super for `compile_world` only when `NEBIUS_LIVE=1`. The public sandbox leaves that flag off, so the demo failure is found by search over the example fixture, not by a live model.

One live smoke call was made after the local gates passed: Lightning, schema-valid `PlanSpec`, 134 input tokens, 59 output tokens, cost `$0.0000222`.

## ShadowBench

Procedural worlds in three families: travel, scheduling, purchase. Each world has a hidden margin, three shocks, and three actions. The oracle probe set is not shown to the evaluator. Metrics are counts against that probe set. No model grades the answers.

The checked-in run is `shadowbench/results/local-gate`, seeds 1000–1029, `$0`. It is a scripted regression on a monotone generator. It is not a comparison of language models.

| System | Task completion | Undetected failures | Repair success | Mean regret |
| --- | --- | --- | --- | --- |
| direct | 0/30 | 30/30 | 0/30 | 1.0 |
| planner | 0/30 | 30/30 | 0/30 | 1.0 |
| planner_critic | 0/30 | 30/30 | 0/30 | 1.0 |
| shadow_no_search | 0/30 | 30/30 | 0/30 | 1.0 |
| shadow | 30/30 | 0/30 | 30/30 | 0.0 |

Bootstrap intervals on this run are degenerate because every world has the same qualitative outcome. That is a property of the generator, not a field accuracy rate. Read `docs/KNOWN_LIMITATIONS.md` before quoting the table.

## Ablations

`shadow_no_search` is the same catalog and the same nominal constraint check without failure-directed ranking. It commits to the cheap plan and misses every planted failure. The plot is `shadowbench/results/local-gate/plots/ablation.png`.

The gap in the table above does not depend on model size. Lightning versus Super for compilation is a separate study in `shadowbench/compiler-study/`. Ultra was not enabled.

## Live Nemotron Pilot

This is separate from the local scripted gate above. The local gate does not measure Nemotron.

The reported run is `shadowbench/results/live-pilot-20261007T180515Z`. Thirty frozen heterogeneous worlds, seeds 5000–5029, model `nvidia/Nemotron-3_5-Lightning`, temperature 0, thinking disabled. Two earlier folders are kept: the first truncated repair JSON at 256 tokens, and a rerun that mistakenly shortened context after world 5. Prompt text was not edited. `propose_repairs` max tokens was raised from 256 to 512 after that truncation, then the unshrunk pilot was run again. Choice and analyze calls were cache hits.

Direct, planner, and critic see the same compact context: plan, bundle ids, labels, costs, constraint descriptions, unknowns, and facts. They do not see formulas or bounds. Shadow's deterministic engine does. `shadow_no_failure_search` uses that same engine and only the nominal check. The oracle is not sent to any system.

| System | Task completion | Undetected failures | Failure recall | Repair success | Mean regret |
| --- | --- | --- | --- | --- | --- |
| direct_nemotron | 6/30 | 22/26 | 9/30 | 6/30 | 0.800 |
| planner | 8/30 | 22/26 | 8/30 | 8/30 | 0.733 |
| planner_critic | 5/30 | 8/26 | 22/30 | 5/30 | 0.833 |
| shadow_no_failure_search | 8/30 | 22/26 | 8/30 | 8/30 | 0.733 |
| shadow | 30/30 | 0/26 | 30/30 | 30/30 | 0.000 |

Shadow's minimal-cut precision and recall were 1.0 on worlds where the nominal plan was unsafe. Material-edge recall was 1.0 on worlds that had material edges. Planner-critic avoided the nominal plan more often than it selected a safe one: recall 22/30, completion 5/30, false hazards 3/30. The no-search ablation matches the planner, not full Shadow. The gap is the failure search on the typed world, not a better language-model answer.

On the live Alex trip, Nemotron's repair proposals were incomplete and the evaluator marked them infeasible. Search still selected the 11:20 future. The minimal failure set was flight delay and traffic. `street_closure` stayed unknown. Sandbox execution reconciled. Nemotron returned no hazard list on that call.

Recorded session spend is `$0.01838022`. One call before the accounting fix was dropped from the ledger; its usage was not stored. A later debug call with 2,395 input and 256 output tokens cost `$0.00020514` and is inside the recorded total. Prior external spend `$0.02030592` plus the earlier repo call `$0.0000222` puts recorded known spend at `$0.03870834`.

Tavily was not configured. OpenShell prover status remains `prover_unavailable`. Thirty worlds are a pilot, not a conclusive ranking.

In a frozen 30-world synthetic live pilot using Nemotron 3.5 Lightning, full Shadow completed 30/30 tasks and left 0/26 planted unsafe nominal plans undetected. Direct planning, planner, and planner-critic baselines performed substantially worse. The benchmark measures the architectural advantage of an explicit typed world model plus failure-directed search; it is not a field-accuracy estimate.

Ordinary LLM baselines received user-facing evidence. Shadow additionally operates on the typed world representation produced and maintained by its architecture. The no-search ablation uses that same typed world and only the nominal check, and it scored 8/30.

## World Compiler

The generic compiler in `backend/shadow/world/compiler.py` does not recognize hero phrases and does not license fixture constraint ids. The sandbox NYC example uses `backend/shadow/world/example_world.py`, which is a fixture license table, not a claim that the compiler understood an arbitrary plan. With no model call, that table matches source text to the pre-authored travel constraints. It does not choose a flight. `street_closure` stays `UNKNOWN` in that example. A confirmed hotel fact can be `VERIFIED`. Parsed clock time and the $100 cap are `COMPUTED` from the example text. Live `compile_world`, when enabled, is a separate path and is what the compiler study measured.

A later 40-case attack set, `shadowbench/redteam-compiler/`, was frozen before scoring and was not taken from the travel fixture. The generic compiler recalled 0/25 hard constraints. The example table also recalled 0/25, and it over-licensed `c_friday` on an unrelated sentence that merely contained "Friday." Super plus the citation check, one pass, recalled 18/25 hard constraints, 0 false hard constraints, 3/6 dependencies, and 3/8 unknowns, and detected 0/2 contradictions. Cost `$0.00678450`. That label compiler does not emit the expressions the search evaluates.

A separate route, `backend/shadow/world/executable.py`, does emit typed expressions for a documented set of time, duration, and budget sentences. It does not read the travel fixture. Missing durations stay missing. Conflicting values stay conflicting unless one record supersedes the other. `shadowbench/primitive-holdout/` scores that grammar: status 40/40 on the development split and 40/40 on the frozen test split. Those sentences were generated from the forms the compiler implements, so this is a grammar check, not an open-world language result. See `docs/EXECUTABLE_WORLD.md`.

Unfamiliar wording takes a different route. `backend/shadow/world/semantic.py` asks Nemotron Super for facts and links, then accepts a link only when the cited words support the numbers. The deterministic engine evaluates the resulting expressions. On a 40-case frozen set written after development, the grammar compiler produced 0 executable worlds and Super plus the grounder matched the frozen check on 29/40. That set was written by the compiler author, not an independent author. The public demo does not call the model. See `docs/SEMANTIC_GENERALIZATION_AUDIT.md`.

The frozen holdout is `shadowbench/world_compiler_holdout/` (16 cases). One Lightning compile call per case. Oracle labels were frozen before the run. No LLM judged the labels.

| Metric | Result |
| --- | --- |
| HardConstraintRecall | 5/10 |
| FalseHardConstraintRate | 0/8 |
| MaterialDependencyRecall | 1/2 |
| FalseDependencyRate | 0/1 |
| UnknownPreservationRate | 1/2 |
| ProvenanceCoverage | 21/21 |
| EndToEndRepairSuccess | 10/16 |

Additional Token Factory spend for those 16 calls: `$0.00059778`.

## Compile route

A later comparison used new development cases, not the holdout above. The selection rule was frozen first: repair rate, then hard-constraint recall, then a lower false-hard rate, then unknown preservation, then lower cost. Ultra was not used.

| System | Repair | Hard recall | False hard | Unknowns | Spend |
| --- | --- | --- | --- | --- | --- |
| Lightning | 14/20 | 7/13 | 0/12 | 2/3 | $0.00063612 |
| Super (`nvidia/nemotron-3-super-120b-a12b`) | 13/20 | 8/13 | 0/15 | 1/3 | $0.00307590 |
| compiler-verifier | 15/20 | 7/13 | 0/11 | 3/3 | $0.00063612 |

The compiler-verifier is the Lightning proposal plus a deterministic check. It drops unsupported hard claims, moves preference wording out of the hard set, and keeps missing values unknown. It does not make a second model call. That route won and is frozen.

It was then scored once on a new 12-case holdout: repair 10/12, hard recall 6/8, false hard 0/7, dependency recall 1/2, unknowns 1/1, provenance 15/15. That holdout was not used to pick the winner and was not run again.

A later study, `shadowbench/compiler-study/`, compared four architectures on 32 new development cases: Lightning, Lightning plus a Lightning audit, Super, and Super plus a Lightning audit. The audit cannot overwrite the world. A deterministic merge adds a candidate only when the cited record contains the quoted evidence. The test split, 24 cases, was hashed before scoring and scored once.

Selection preferred a low false-hard rate, then hard-constraint recall, then unknown preservation, then repair success, then lower cost. Ultra was not used.

| Architecture | Hard recall | False hard | Unknowns | Repair | Fair cost |
| --- | --- | --- | --- | --- | --- |
| Lightning | 10/17 | 0/18 | 1/6 | 21/32 | $0.00092208 |
| Lightning + Lightning audit | 10/17 | 0/28 | 1/6 | 21/32 | $0.00166506 |
| Super | 14/17 | 0/22 | 0/6 | 23/32 | $0.00410550 |
| Super + Lightning audit | 14/17 | 0/37 | 0/6 | 23/32 | $0.00477840 |

Super won. The audit did not raise recall, unknown preservation, or repair, and it proposed more hard constraints, so it is not the default compile path. Ordinary plan and repair calls stay on Lightning. Live compilation uses Super only for `compile_world`, and only when `NEBIUS_LIVE=1`. The public sandbox stays on the deterministic compiler.

The frozen test split, scored once: hard recall 10/13, false hard 0/18, dependency recall 3/4, unknowns 1/4, provenance 23/23, contradiction detection 0/2, repair 19/24. Test spend `$0.00373350`. Compiler-study spend for this pass, including the five-case probe, was `$0.01129200`.

## Adversarial Holdout

`shadowbench/adversarial_holdout/` has 10 hand-authored scenarios, written before the run and not edited afterward. Same repair engine. No model tokens.

| System | Task completion | Repair success | Mean regret |
| --- | --- | --- | --- |
| shadow | 9/10 | 9/10 | 0.100 |
| shadow_no_failure_search | 7/10 | 7/10 | 0.300 |

Failure recall on the cases with a planted cut: 6/6. False hazards: 0/10. Unknown handling: 10/10. The miss is `non_monotonic`: Shadow selected the larger-radius repair, and the frozen oracle had named the cheaper medium repair. That ranking order is the engine's documented order. The holdout was not changed to match it.

These four numbers answer different questions: the local scripted gate, the live Lightning pilot, this compiler holdout, and this hand-authored holdout.

## Security model

`docs/THREAT_MODEL.md`. Fail closed on bad model output, broker denial, verification mismatch, and a stale contract.

## Privacy model

Fixtures are fictional. The model context drops raw source bodies. Logs store hashes, token counts, and schema validity, not the raw prompt, unless `SHADOW_LOG_RAW_PROMPTS=true`.

## Quickstart

Python 3.12 and Node 22.

```bash
make setup
make dev
```

Open `http://127.0.0.1:8000` after `make build`, or run the Vite dev server:

```bash
cd frontend && npm run dev
```

Vite proxies `/api` to port 8000. Start `make dev` first.

## Environment variables

Copy `.env.example`. Names only. The sandbox demo ignores empty values.

`NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL`, `NEBIUS_LIVE`, `NEBIUS_PROJECT_BUDGET_USD`, `ALLOW_SUPER`, `ALLOW_ULTRA`, `TAVILY_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `DUFFEL_ACCESS_TOKEN`, `SHADOW_REAL_ACTIONS_ENABLED`.

## Run the sandbox demo

Leave the defaults. The badge reads `SANDBOX`.

The primary box is freeform. Type a plan and press **Analyze my future**. Shadow sends that text through the World Compiler. It builds an executable Future Graph only when the request has grounded records and an executable structure. If a plan looks modelable but the records are missing, Shadow lists the missing information. If it cannot be modeled with the connected tools, Shadow says so. It does not invent a graph, a probability, or a tool action.

**NYC trip** and **Apartment move** are deterministic examples. Each chip fills the textarea and attaches its synthetic context. Press **Analyze my future** after the chip. The apartment example uses the same engine: a lease overlap, a Thursday commitment, and cash.

1. Click **NYC trip**, then **Analyze my future**.
2. Read the future bugs, the minimal failure, and the future diff.
3. **Approve repaired future.**
4. **Execute sandbox actions.** The final line is `Observed state matches approved future`.
5. **Try unrelated change.** The broker blocks it.
6. **+74 min delay** recomputes and keeps authority. **Fare +$80** or **Hotel canceled** revokes it.

## Run tests

```bash
make test
```

Backend coverage on the deterministic core is enforced at 85%. The latest local run is 90%. CI does not set `NEBIUS_LIVE`.

Frontend unit tests are Vitest. The Playwright script is `frontend/e2e/hero.spec.ts`:

```bash
cd frontend && npx playwright install chromium && npm run e2e
```

## Run ShadowBench

```bash
make benchmark-local
```

Results land in `shadowbench/results/local-gate` and a copy of the summary in `shadowbench/results/latest`.

## OpenShell

`openshell/boundary.yaml` is the operator maximum. The candidate policy is compared locally. `openshell-prover` was not installed here, so the displayed status is `prover_unavailable`, not formally verified. The app runs without it.

## Known limitations

`docs/KNOWN_LIMITATIONS.md`.

## Hackathon disclosure

Built for the Nebius x NVIDIA Global AI Hackathon, personal AI track. License Apache-2.0. Devpost copy is `docs/DEVPOST_SUBMISSION.md`. The demo video still has to be recorded from `docs/DEMO_SCRIPT.md` and uploaded with the form. Judge feedback belongs on that form.

NemoClaw is not integrated. OpenShell is the system boundary, and the broker is what knows which event was approved. A second sandbox would not change that decision.

## License

Apache-2.0. See `LICENSE`.
