# Red team

Hostile review of Shadow at `7f116f1`. Findings below are what a judge can verify in the tree. Status is updated when a later commit fixes or explicitly accepts the item.

## RT-01

- ID: RT-01
- area: public demo
- severity: CRITICAL
- exploitability / likelihood: high on the single Render process
- judge impact: DISQUALIFYING
- affected judging criterion: security, Personal AI privacy, demo reliability
- exact claim being challenged: a visitor's futures stay private
- evidence: `create_app` builds one `PlanService` and one in-memory `EventLog`. Every route reads `app.state.service`. `POST /api/demo/reset` clears that shared object.
- reproduction: client A analyzes a plan. Client B `GET /api/plans/{id}` with A's id and receives A's graph. Client B `POST /api/demo/reset` drops A's plans.
- whether failure is real or theoretical: real
- proposed fix: unguessable per-browser session cookie. Reset and plans stay inside that session.
- status: resolved. `SessionStore` issues an HttpOnly cookie. A second client cannot read or reset the first.

## RT-02

- ID: RT-02
- area: world compiler
- severity: HIGH
- exploitability / likelihood: certain if a judge reads `compiler.py`
- judge impact: MAJOR_SCORE_LOSS
- affected judging criterion: technical implementation, NVIDIA necessity, novelty
- exact claim being challenged: messy personal context is compiled into a typed world
- evidence: `_LICENSES` maps `("dinner", "7")` to `c_dinner`, `("maximum additional", "100")` to `c_budget` with value `100`, and `("design review", "cannot move")` to `c_review` and `c_leave`. `flight_to_exit` and `exit_to_dinner` are appended whenever those fixture ids exist. `street_closure` is inserted when the words are absent.
- reproduction: `compile_bundle(load_bundle("travel"))` with no model call returns `c_dinner` in `licensed_constraint_ids`.
- whether failure is real or theoretical: real
- proposed fix: move that table into an explicitly named example adapter. The generic compiler validates citations, numbers, and schema only.
- status: resolved. The table lives in `example_world.py` and is attached only for the travel fixture. Generic `compile_bundle` recalled 0/25 hard constraints on the attack set. Super plus verification recalled 18/25 with 0 false hard constraints.

## RT-03

- ID: RT-03
- area: NVIDIA necessity
- severity: HIGH
- exploitability / likelihood: certain on the public demo
- judge impact: MAJOR_SCORE_LOSS
- affected judging criterion: sponsor relevance
- exact claim being challenged: Nemotron interprets the context the demo searches
- evidence: Render sets `NEBIUS_LIVE=0`. `attach_compiled` then uses the keyword adapter. Search reads `fixtures/travel/world.json`.
- reproduction: public `/api/plans/freeform` with the NYC example returns `b1120` with zero model calls.
- whether failure is real or theoretical: real
- proposed fix: say this in the README. Do not describe the sandbox path as a live compile. Keep Super behind `NEBIUS_LIVE=1` for `compile_world` only, which is what the compiler study measured.
- status: accepted. The README states the public path is the example fixture. Super is used only for live `compile_world`.

## RT-04

- ID: RT-04
- area: benchmarks
- severity: HIGH
- exploitability / likelihood: certain if the README is skimmed
- judge impact: MAJOR_SCORE_LOSS
- affected judging criterion: evaluation credibility
- exact claim being challenged: 30/30 shows Shadow beats planners
- evidence: `shadowbench/results/local-gate` is a monotone generator and scripted baselines. The live pilot gives Shadow formulas and bounds the model baselines do not get. README line "Lightning versus Super was not run" is false after `shadowbench/compiler-study/`. README also says this build did not turn Super on.
- reproduction: read `README.md` against `shadowbench/compiler-study/decision.json` and `docs/KNOWN_LIMITATIONS.md`.
- whether failure is real or theoretical: real
- proposed fix: label the local gate as a regression. Point model comparison at the compiler study. State that a fair raw-context search benchmark cannot exist until the compiler emits executable formulas; the fixture still supplies those.
- status: resolved in README, `docs/FAILURE_CASES.md`, and `docs/JUDGE_QA.md`. The fair search benchmark was not fabricated.

## RT-05

- ID: RT-05
- area: watcher
- severity: HIGH
- exploitability / likelihood: medium
- judge impact: MAJOR_SCORE_LOSS
- affected judging criterion: always-on correctness
- exact claim being challenged: an unknown event is scoped to futures that depend on it
- evidence: `FutureWatcher.process_event` applies `unknown_drift` to every loaded approved future when `epistemic_status == "UNKNOWN"`, before dependency checks.
- reproduction: two approved futures. An unknown event whose entities miss one scenario still marks that future UNKNOWN.
- whether failure is real or theoretical: real
- proposed fix: use `depends_on` first. Unrelated futures stay UNCHANGED.
- status: resolved. An unknown event whose entity is not a travel variable leaves the approved future UNCHANGED. `flight_delay_min` still becomes UNKNOWN.

## RT-06

- ID: RT-06
- area: skills
- severity: MEDIUM
- exploitability / likelihood: high
- judge impact: MINOR_SCORE_LOSS
- affected judging criterion: does not overclaim generality
- exact claim being challenged: skill selection is a match, not a default bucket
- evidence: `SkillRegistry.available_for` returns Coordinate Schedule when nothing matches.
- reproduction: `available_for("hello")` is Coordinate Schedule.
- whether failure is real or theoretical: real
- proposed fix: return no skill. Freeform already treats no keyword match as UNSUPPORTED.
- status: resolved. `available_for("hello")` is None.

## RT-07

- ID: RT-07
- area: prompt injection
- severity: MEDIUM
- exploitability / likelihood: low on the sandbox path, real if live compile is on
- judge impact: MINOR_SCORE_LOSS
- affected judging criterion: security
- exact claim being challenged: calendar and mail text cannot become instructions
- evidence: records are JSON in the user message. The compile prompt does not say they are untrusted. Authority still goes through the broker, which ignores record text.
- reproduction: a record containing "Ignore previous instructions" is not an action id. The broker still denies `update_exam`.
- whether failure is real or theoretical: theoretical for execution, real for a sloppy compile prompt
- proposed fix: delimit evidence in `compile_world.txt`. Test that injection text does not license a hard constraint or an action.
- status: resolved for the sandbox path. The compile prompt tells the model that records are untrusted evidence. The injection test does not produce a hard constraint and `update_exam` stays unauthorized. Live Super was not re-prompted after the attack-set score.

## RT-08

- ID: RT-08
- area: privacy copy
- severity: MEDIUM
- exploitability / likelihood: certain
- judge impact: MINOR_SCORE_LOSS
- affected judging criterion: privacy
- exact claim being challenged: "Shadow keeps a private model"
- evidence: public process memory, no device-local store, live compile would send record text to Nebius. No personal Google data is connected.
- reproduction: read the README lead against `create_app`.
- whether failure is real or theoretical: real
- proposed fix: replace the sentence with what is actually true.
- status: resolved. The README describes a per-browser sandbox on the server, not a private device store.

## RT-09

- ID: RT-09
- area: execution
- severity: LOW
- exploitability / likelihood: covered by existing tests
- judge impact: COSMETIC
- affected judging criterion: reliability
- exact claim being challenged: a provider can report success without changing state, or time out after commit
- evidence: `test_provider_lie_halts` expects `verify_mismatch`. `test_timeout_then_retry_is_idempotent` expects one mutation.
- reproduction: `pytest backend/tests/test_runtime.py`
- whether failure is real or theoretical: the failure mode is tested; the product behavior holds
- proposed fix: none beyond keeping the tests
- status: accepted, already tested

## RT-10

- ID: RT-10
- area: fair end-to-end benchmark
- severity: HIGH
- exploitability / likelihood: certain
- judge impact: MAJOR_SCORE_LOSS
- affected judging criterion: evaluation
- exact claim being challenged: held-out evidence shows the full loop on raw context
- evidence: search consumes `Scenario` formulas from fixtures or the benchmark generator. The compiler emits labels, not executable expressions. Giving every system the same emails and then letting only Shadow read `world.json` would repeat the live-pilot asymmetry.
- reproduction: `license_scenario` filters fixture constraints. It does not synthesize them.
- whether failure is real or theoretical: real
- proposed fix: do not invent a benchmark that still feeds Shadow hidden formulas. Document the blocker. The compiler study remains the raw-text measurement.
- status: accepted, blocker documented

## RT-11

- ID: RT-11
- area: model routing
- severity: MEDIUM
- exploitability / likelihood: the published costs were cache-shared
- judge impact: MINOR_SCORE_LOSS
- affected judging criterion: model choice
- exact claim being challenged: Super plus audit was almost free
- evidence: `compiler-study` dev results record `measured_cost_usd` separately because audit arms reused cached compile calls. The decision file explains the correction. Quality tie (same recall, same false-hard rate) then preferred the cheaper Super-only arm. False-hard rate was 0 for every arm. Unknown preservation was worse for Super (0/6 versus 1/6).
- reproduction: read `shadowbench/compiler-study/dev/results.json` field `selection_note`.
- whether failure is real or theoretical: the selection bug was real and was corrected before the test split. The test split was not used to choose.
- proposed fix: leave the frozen files untouched
- status: accepted

## RT-12

- ID: RT-12
- area: cross-plan
- severity: LOW
- exploitability / likelihood: the demo pair is synthetic
- judge impact: MINOR_SCORE_LOSS
- affected judging criterion: product depth
- exact claim being challenged: cross-plan reasoning is only an effect-dictionary diff
- evidence: `cross_plan_conflicts` also checks time overlap, an explicit shared budget, protected claims, and reservation state. The gallery pair is fixture data, not a UI branch. It is not a joint planner and it does not scale by indexing.
- reproduction: `pytest backend/tests/test_futures.py`
- whether failure is real or theoretical: the shallow claim is outdated; the joint-planner claim would still be false
- proposed fix: keep the claim at typed conflicts. Do not say the futures are planned together.
- status: accepted

## RT-13

- ID: RT-13
- area: request size
- severity: MEDIUM
- exploitability / likelihood: easy
- judge impact: MINOR_SCORE_LOSS
- affected judging criterion: reliability
- exact claim being challenged: a huge plan cannot pin the process
- evidence: `FreeformIn.text` is an unbounded string. Analysis of the example worlds is CPU-heavy.
- reproduction: `POST /api/plans/freeform` with a 100k-character body.
- whether failure is real or theoretical: real
- proposed fix: reject text over 8,000 characters with 422.
- status: resolved. An 8,001-character body returns 422.

## RT-14

- ID: RT-14
- area: persistence
- severity: MEDIUM
- exploitability / likelihood: certain on Render restart or spin-down
- judge impact: MINOR_SCORE_LOSS
- affected judging criterion: always-on memory
- exact claim being challenged: approved futures survive restart
- evidence: the event database is `sqlite://` memory. Render's disk is ephemeral. A restart drops plans even though `ContractRow` would restore them inside one process.
- reproduction: new process, `GET /api/futures` shows only the synthetic demo pair.
- whether failure is real or theoretical: real
- proposed fix: do not claim cross-restart memory for the public demo. A durable store is out of scope for this pass.
- status: accepted
