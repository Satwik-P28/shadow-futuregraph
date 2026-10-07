# Semantic generalization audit

Audited at `184ad757b6bb1c85a43d88febc5682c2b46e3118`, before the live unfamiliar-plan probe. This describes the code path. It does not claim a model result.

## Path from raw text to an expression

1. Freeform text with no demo id calls `compile_primitives` in `backend/shadow/world/executable.py`.
2. That function splits on newlines and periods and matches a fixed set of sentence forms (`starts at`, `ends at`, `arrives at`, `X to Y takes N-M minutes`, `costs $N`, `budget is at most $N`).
3. Matched spans become `VariableIR` / `ConstraintIR` values. Clocks become minutes. Ranges become exogenous variables.
4. `Expr` is built only from `var`, `const`, `add`, and `sub`, then compared with `lte` / `gte` / `lt` / `gt` / `eq` / `neq`.
5. `evaluate_repairs` and `search_failures` run on that `Scenario`.
6. The NYC and apartment buttons never enter this path. They load fixture JSON and `example_world.py`.

`compile_executable.txt` and `ExecutableProposal` exist for a model, but freeform does not call them. `NEBIUS_LIVE` is off on the public demo. FakeNemotron returns an empty proposal for that purpose.

## What each layer actually does

| Question | Answer |
| --- | --- |
| What does Nemotron handle today? | Nothing on the product path. A live call is possible only if something invokes `compile_executable` with `NEBIUS_LIVE=1`. The schema it must fill is the same variable/constraint/action JSON the grammar builds. |
| What does deterministic parsing handle? | Clock times, minute ranges, dollar amounts, "cannot move", "cannot cancel", and an explicit `Name to Other takes` link. |
| What requires a sentence pattern? | Every executable chain. "quarter past four", "half an hour", "around seven", and "I can't get there after five" do not match. |
| What requires predefined variable names? | The grammar slugs the noun phrase in the sentence. It does not have a table of `class_end` or `dinner`. Two phrasings of the same event do not unify unless the leftover noun text matches. |
| What requires a pre-authored dependency? | The link exists only when a sentence matches `A to B takes`. The model is not asked to propose `station_arrival = class_end + parking + drive` on the product path. |
| What requires fixture actions? | The NYC repair catalog. The grammar path only offers `plan.keep`, `plan.drop_purchase`, and `plan.select_option` when the sentence states an alternate time or an unlocked purchase. |
| What causes abstention? | No matched sentence. Two timed events and no `to ... takes` sentence. A budget with no cap, or a cap with no prices. Two different values for the same field when neither record supersedes the other. |
| What can pass unnoticed? | An empty model proposal validates as `READY` with a keep action and no constraints. "Usually" and "around" are not distinguished from hard ranges because those words never parse. "Half an hour" is invisible, so a real 30-minute exit is treated as missing. A later email does not win over an earlier calendar unless the record carries a `supersedes` id. The product path never sets that id from prose. |

## Verifier limits

`validate_proposal` checks source ids, whether a number or clock in the cited text supports a float, unit tags on formula args, cycles, and the action allowlist. It returns one status, `READY` or `UNSUPPORTED`, plus a string list. It does not return `NEEDS_INFORMATION` or `CONTRADICTORY`. It does not parse "half an hour", "quarter past", or "around seven". It cannot represent overlap, exclusivity, or `if rain`. Those operators exist on `Expr` (`if`) but not on `FormulaIR`.

A number that is only implied by words fails grounding. That is safe and also blocks the legitimate reading of "half an hour".

## Benchmark that does not show generalization

`shadowbench/primitive-holdout/` is 40/40 because `scripts/primitive_holdout.py` emits the same sentence forms the matcher accepts. It is a regression for that matcher.

## Cost ledger at audit time

Repo ledger `0.04120818`. Repo soft cap `0.25`. Overall cap `1.00`. No reservation was open. The live probe below must stay inside the remaining repo soft cap. The extra experiment ceiling of `$5` does not raise the code cap.

## What the live passes showed

The grammar compiler returned UNSUPPORTED on all 10 development plans and on all 40 frozen plans. It never saw "half an hour", "quarter past four", or a budget written as ordinary sentences.

The first Super call used `ExecutableProposal`. Nine of ten responses failed schema validation because variables omitted required fields. One response was an empty object, which the old validator treated as ready. That file is `shadowbench/semantic-explore/live.json`. Cost `$0.0019668`. Prompt hash `d4baa76d22f8c045`.

The semantic schema asks for surface quotes, not pre-typed variables. A development pass on the same ten plans, prompt hash `17228dc34eb2e73b`, cost `$0.0041778`, is `shadowbench/semantic-dev/live-r2.json`. Super extracted the clocks, ranges, and prices. It emitted a sum for the flight and the class-to-train cases, and the engine found the high-end failure in both. It did not emit the car-overlap link. It abstained on the unconfirmed dinner, the two interview times, the missing transfer, and the conditional ceremony.

No second model call was added. The measured gap is omitted links, and a verifier must not invent them.

## Frozen 40

`shadowbench/semantic-holdout/cases.json`, sha256 `e5496d88ac73d40b9cdaafa05121fed2292f3c9886dbea182dfdcc4ea29628a6`. Scored once. Model `nvidia/nemotron-3-super-120b-a12b`. Same prompt hash. Cost `$0.0161856`.

| Check | Result |
| --- | --- |
| Grammar executable | 0/40 |
| Schema valid | 40/40 |
| Frozen check matched | 29/40 |
| Abstention on underspecified cases | 11/11 |
| Contradiction | 5/6 |
| Range failure found | 5/8 |
| Budget overflow | 3/4 |
| Feasible plan left feasible | 3/4 |
| Overlap or direct schedule conflict | 2/7 |

The 11 misses are recorded in `live.json`. Four are missing `overlaps` or `sum_at_most` links after the numbers were extracted. Others are the model treating a stated duration as unknown, or "at five" failing the digit clock parser. A later parser change accepts hour words such as "at five". The frozen file was not re-scored after that change.

This set was written by the same person who wrote the compiler, after seeing the development failures. It is not an independent human author. It is also not the grammar-template set.

## Product path

Freeform text calls this compiler only when `NEBIUS_LIVE=1` and no example context is selected. The public service leaves that flag off. Example NYC and apartment buttons still load their fixtures. The inspection panel renders only the records the grounder returned.
