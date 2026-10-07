# Demo script

Target length 2:40–2:55. The app is the sandbox demo. The badge says SANDBOX. No API key is required.

0:00–0:12 Hook
Your AI can make a perfectly reasonable plan that still breaks your life.

0:12–0:28 User
The box is empty. The two chips under it are examples, not the product. Click **NYC trip**. The textarea fills with "Move my NYC trip to Friday and make sure everything still works." Then click **Analyze my future**.

0:28–0:48 World Compiler
Show the ordinary records: Friday design review, Friday 7 PM dinner, the algorithms exam, the dinner email, the existing trip, the ride linked to the old flight, and the $100 cap. Say: Nemotron converts messy personal context into candidate goals, constraints, dependencies, and unknowns. The model structures the problem. Shadow does not trust the model to prove the plan is safe.

0:48–1:05 Future Graph
The afternoon flight is nominally valid. It is the cheapest plan that still reaches dinner if nothing goes wrong.

1:05–1:25 Failure search
Show flight delay plus traffic. Together they violate the dinner constraint. Say: Nemotron itself missed this hazard in our live run. Shadow still found it.

1:25–1:45 Repair
The search selects the 11:20 flight. Show the Future Diff: flight 14:40 to 11:20, ride 12:05 to 8:45, incremental cost +$76. Hotel, dinner, review, and exam stay put.

1:45–1:55 Approve
Click **Approve repaired future**.

1:55–2:10 Execution
Execute the sandbox flight, ride, and calendar updates.

2:10–2:22 Attack
Click **Try unrelated change**. The algorithms exam is blocked. The line is "Blocked: action is outside the approved future."

2:22–2:40 Always-on
Do not retype the plan. Point at Shadow Watch: it is monitoring the approved future, and dinner is protected from saved commitment memory. **+74 min delay** is a world event. The future still holds. **Fare +$80** is another world event. Shadow Watch reports drift, the contract goes stale, and authority is revoked. The repair waits for approval. This is event-driven, not a background poll of every service.

2:35–2:42 Reconciliation
"Observed state matches approved future."

2:42–2:55 Benchmark
In a 30-world Lightning pilot, ordinary model planning repeatedly selected nominally valid but fragile plans. Full Shadow completed 30/30 with no planted failures left undetected. This is a synthetic pilot, not a field-accuracy claim. If there is time, flash the World Compiler holdout and the 10-world adversarial holdout. Shadow was 9/10 on that holdout.

End on: Your AI shouldn't just execute your plan. It should find the bugs in your future first.
