# Demo script

Target length 2:40–2:50. The app is the sandbox demo. Say "sandbox" when the badge says sandbox.

0:00–0:10
Plans fail because of consequences you did not think to check.

0:10–0:25
Type, or leave, "Move my NYC trip to Friday and make sure everything still works." Alex is synthetic. Hit **Check the Friday trip**.

0:25–0:50
The future graph is the current trip, the Friday dinner at 19:00, the fixed design review, the ride, and the cost cap. One material unknown stays unresolved. No probability is shown for it.

0:50–1:10
The afternoon flight is the cheapest plan that still reaches dinner if nothing goes wrong. Shadow marks it as a future bug. Trace delay and ground traffic into the dinner constraint.

1:10–1:30
The minimal failure is the pair. Either perturbation alone, at that size, still makes dinner. Together they miss it. The 17:10 flight misses dinner with no perturbation at all. Moving dinner is proposed and rejected.

1:30–1:45
The evaluator reruns the search on each repair. The 11:20 flight has a much larger failure radius. It costs more. The ranking prefers the radius.

1:45–2:00
Future diff: flight 14:40 → 11:20, ride 12:05 → 8:45, hotel unchanged, dinner unchanged, design review unchanged, exam unchanged, incremental cost +$76. Click **Approve repaired future**.

2:00–2:15
Sandbox execution changes the flight, the ride, and the trip event. Then click **Try unrelated change**. The broker blocks the algorithms exam. The line is "Blocked: action is outside the approved future."

2:15–2:25
Inject **+74 min delay**. The assumption is invalidated and the graph is recomputed. The approved future still holds, so authority stays. Then, if you want the revoke, inject **Fare +$80**. The cost cap breaks, the contract goes stale, and execution halts.

2:25–2:35
Before the breaking inject, the final line is "Observed state matches approved future."

2:35–2:45
Open ShadowBench. Thirty local worlds. Full Shadow completes 30/30 with 0 undetected failures. The same architecture without failure-directed search completes 0/30. Say that this run did not spend model tokens.

2:45–2:50
Nemotron proposes structure. The deterministic core searches and ranks. The broker scopes the future. OpenShell is the system boundary when the prover is present. Tavily is the live evidence adapter when a key is present.

End line: Your AI shouldn't just execute your plan. It should find the bugs in your future first.
