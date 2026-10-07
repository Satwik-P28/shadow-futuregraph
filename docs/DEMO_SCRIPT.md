# Demo script

Target length 2:40–2:55. The app is the sandbox demo. The badge says SANDBOX. No API key is required.

0:00–0:10 Hook
Your plans don't fail one at a time. They collide with the rest of your life.

0:10–0:25 Futures home
The sandbox already shows two saved futures for Alex: NYC airport window and Gallery opening. Each is feasible on its own.

0:25–0:35 Cross-plan conflict
Click **1 cross-plan conflict**. The overlap is Alex from 2:00–5:00 PM and the protected gallery opening from 3:00–4:00 PM. Say: this plan works alone, but conflicts with another future.

0:35–0:50 NYC future
Click **NYC trip**, then **Analyze my future**. The textarea is the plan. Say: Nemotron interprets messy personal context. Shadow turns that into a typed world and deterministically searches for ways the plan can fail.

0:28–0:48 World Compiler
Show the ordinary records: Friday design review, Friday 7 PM dinner, the algorithms exam, the dinner email, the existing trip, the ride linked to the old flight, and the $100 cap. Say: Nemotron converts messy personal context into candidate goals, constraints, dependencies, and unknowns. The model structures the problem. Shadow does not trust the model to prove the plan is safe.

0:48–1:05 Future Graph
The afternoon flight is nominally valid. It is the cheapest plan that still reaches dinner if nothing goes wrong.

1:05–1:25 Failure search
Show flight delay plus traffic. Together they violate the dinner constraint. Say: Nemotron itself missed this hazard in our live run. Shadow still found it.

1:15–1:25 Future Lab
Open Future lab. Move flight delay. The hard constraint holds, then it does not. Click **Find nearest failure**. Say this is a local simulation. It does not call the model and it does not execute anything.

1:25–1:45 Repair
The search selects the 11:20 flight. Show the Future Diff: flight 14:40 to 11:20, ride 12:05 to 8:45, incremental cost +$76. Hotel, dinner, review, and exam stay put.

1:45–1:55 Approve
Click **Approve future**.

1:55–2:10 Execution
Execute the sandbox flight, ride, and calendar updates.

2:10–2:22 Attack
Click **Try unrelated change**. The algorithms exam is blocked. The line is "Blocked: action is outside the approved future."

2:22–2:40 Always-on
Do not retype the plan. Point at Shadow Watch: it is monitoring the approved future, and dinner is protected from saved commitment memory. Open **Inject world change**, then **+74 min delay**. The future still holds. **Fare +$80** is another world event. Shadow Watch reports drift, the contract goes stale, and authority is revoked. The repair waits for approval. This is event-driven, not a background poll of every service.

2:35–2:42 Reconciliation
"Observed state matches approved future."

2:42–2:55 Benchmark
In a 30-world Lightning pilot, ordinary model planning repeatedly selected nominally valid but fragile plans. Full Shadow completed 30/30 with no planted failures left undetected. This is a synthetic pilot, not a field-accuracy claim. If there is time, flash the World Compiler holdout and the 10-world adversarial holdout. Shadow was 9/10 on that holdout.

End on: Your AI shouldn't just execute your plan. It should find the bugs in your future first.
