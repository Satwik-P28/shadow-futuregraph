# Threat model

| Threat | Mitigation | Residual risk |
| --- | --- | --- |
| Prompt injection in a retrieved fact | Facts are data. Action ids must already exist in the catalog. Unknown ids are dropped. | A future author could mistakenly treat fact text as instructions. The current pipeline does not. |
| Malicious retrieved content | Model output must match a Pydantic schema. One JSON repair, then fail closed. | A schema-valid but harmful repair can still be proposed. The evaluator and broker have to reject it. |
| Stale evidence | Injected observations rewrite baselines, mark assumptions invalidated, and re-check invariants. | An unmodeled fact never enters the graph. |
| Hallucinated dependency | Inferred edges stay `INFERRED`. Hard authorization uses the typed world, not the inferred edge alone. | A user can still approve a future that rests on a bad inferred story. The diff shows unknowns. |
| Overbroad permission | Broker binds type and resource. OpenShell bounds hosts and filesystem paths. | OpenShell does not understand calendar identity. A missing prover is not a proof. |
| Credential leakage | Environment variables only. `.env` is ignored. The secret scan refuses common key shapes. | A developer can still paste a key into a commit. The scan is pattern-based. |
| Tool misuse | No model-authored shell or Python is executed. | Adapters that shell out later would need their own allowlist. |
| Duplicate execution | Idempotency key is `contract_id:action_id`. A stored result is returned instead of applying again. | A provider that ignores idempotency outside the sandbox can still double-charge. Duffel orders are not placed by the demo. |
| Partial execution | Calendar failure after a committed flight retries the calendar step and does not automatically undo the flight. | Some partial states are left for the user on purpose, because compensation can make them worse. |
| Provider lie | `verify()` rereads provider state. A success flag with unchanged state halts and does not claim success. | A provider that lies consistently on read and write will pass verification. |
| World drift | Material assumption changes mark the contract stale and block further execution. | Drift inside the modeled slack does not revoke authority. `+74` minutes on the early flight is an example. |
| Unsafe retry | A timeout after a commit reconciles the stored result. It does not send a second mutation. | Ambiguous failures with no stored result halt. |

Execution fails closed when the model output is invalid, the constraint engine cannot evaluate, verification mismatches, or the contract is stale.
