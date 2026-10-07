# Failure cases

These are misses and limits a judge can check. They are not patched into successes.

## Example adapter is not a compiler

`license_example_bundle` maps fixture phrases onto pre-authored constraint ids. On the 40-case red-team set it recalled 0/25 hard constraints. It did license `c_friday` for the unrelated sentence "Friday could be packed" because the needle is the single word `friday`. That function is only attached to the travel example scenario. Pointing it at arbitrary mail would over-license. The generic `compile_bundle` recalled 0/25 on the same set and proposed no hard constraints.

## Super plus verifier, same frozen set

Scored once, after the set was hashed, with no prompt edit afterward. Hard recall 18/25. False hard 0/25 proposed. Dependency recall 3/6. Unknowns 3/8. Contradiction detection 0/2. Repair proxy 28/40. Spend `$0.00678450`. The model is necessary for this text. It is not sufficient, and it still misses negations, units, and contradictions.

## Non-monotonic adversarial holdout

`shadowbench/adversarial_holdout` case `non_monotonic`: the search picked the larger-radius repair and the frozen oracle named the cheaper medium repair. The ranking prefers radius before cost. The case was not edited. Shadow is 9/10 on that holdout.

## Live pilot is not an equal-input comparison

The 30-world Lightning pilot gives Shadow the typed scenario. The model baselines see user-facing evidence, not the formulas and bounds. Shadow's 30/30 is an architecture result on that split, not proof that Nemotron failed a fair reading test. The local gate's 30/30 is a monotone scripted regression.

## No executable compiler

The compiler emits labels. It does not emit the expressions the search evaluates. A fair raw-context benchmark of the full loop would require that missing step. It was not fabricated by feeding `world.json` only to Shadow.

## Public memory does not survive restart

The event log is in-memory SQLite. A Render restart or spin-down drops plans. The demo does not claim device-local or durable personal memory.

## Integrations that are not demonstrated

Google Calendar, Gmail, Duffel, and Tavily are unconfigured. OpenShell's prover is not installed. Status stays `prover_unavailable`.
