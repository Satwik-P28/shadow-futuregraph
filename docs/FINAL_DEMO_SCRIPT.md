# Final demo script

**Target:** 2:40–2:55  
**Execution mode:** public sandbox (`SANDBOX`, no API key)  
**Important:** This script does not present the prepared world as a live Nemotron result.

## 0:00–0:15 — The problem

“AI can make a plan. But what happens when that plan collides with the rest of your life? Shadow finds bugs in a future before you commit to it.”

## 0:15–0:35 — Grounded context

Open the NYC sandbox future. Show the records for the protected dinner, design review, exam, existing trip, linked ride, and fare cap.

“This is a prepared synthetic world for a reliable public demo. The records are the evidence; Shadow does not invent constraints or treat a model response as proof.”

## 0:35–1:05 — Failure discovery

Run **Analyze my future** and show the afternoon flight as the nominally cheapest feasible choice.

“The flight works if nothing goes wrong. Shadow searches nearby futures and finds that a flight delay combined with extra ground time misses the protected dinner. Neither perturbation alone is enough, but together they break the invariant.”

## 1:05–1:30 — Repair comparison

Show the recommended early flight and the future diff.

“Shadow evaluates grounded alternatives deterministically. The repaired future changes the flight and its linked ride, while preserving the dinner, review, exam, and budget constraints.”

## 1:30–1:45 — Approval

Open the Future Contract and approve it.

“Approval is scoped to these named state changes. It is not a general calendar or travel permission.”

## 1:45–2:05 — Sandbox execution and verification

Execute the approved future and show the reconciliation receipt.

“The sandbox provider was mutated only through the approved contract. Shadow reads the resulting state back and reports success only when it matches.”

Attempt the unrelated exam change.

“An action outside the contract is blocked, even though it is the same kind of calendar operation.”

## 2:05–2:35 — Shadow Watch

Inject a delay that the repaired future survives, then inject the fare increase that breaks the budget invariant.

“Shadow Watch rechecks only futures that depend on the changed fact. When the approved future becomes unsafe, its contract goes stale and authority is revoked. A new repair still requires approval. This demo uses an explicitly labeled injected sandbox event; it is not a claim of continuous polling.”

## 2:35–2:55 — Thesis and limits

“Shadow does not replace deterministic checks with confident language. Nemotron can structure messy evidence when live mode is configured; the public route remains deterministic and safe. Shadow turns that evidence into a searched future, a scoped approval, a verified action, and a watchable outcome.”

“Your AI should not just execute your plan. It should find the bugs in your future first.”

