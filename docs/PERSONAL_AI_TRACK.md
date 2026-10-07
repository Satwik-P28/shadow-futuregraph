# Personal AI track

Shadow is event-driven. It watches approved futures when a connected source emits a world event. It does not poll every service, and it does not see changes from tools that are not connected.

| Requirement | Shadow |
| --- | --- |
| Always-on | Shadow Watch loads approved futures and reacts to world events. A valid future stays authorized. An invalid one becomes STALE, authority is revoked, and a repair waits for approval. |
| Private | The world model stays local. Raw source bodies are not sent to the model. Provider state is explicit. |
| Persistent memory | Temporal facts carry a memory kind: commitment, preference, relationship, reservation, responsibility, decision, or approved future. Approved contracts are stored in the same event database and can be monitored after a restart. |
| Reusable skills | Reschedule Trip, Handle Trip Disruption, and Coordinate Schedule are typed manifests with preconditions, effects, verification, and compensation. They do not choose a flight and they do not authorize an action. |
| Chosen tools | Connected-tool status reports calendar, mail, and travel as SANDBOX in this demo, and search as OFF unless Tavily is configured. |
| Cross-workflow execution | Travel, calendar, mail, and search adapters share one future engine. The semantic broker limits execution to the approved contract. |
| NVIDIA model | Ordinary plan and repair calls use Nemotron 3.5 Lightning. A measured compiler study selected Super for live `compile_world` only. The public sandbox does not make that call. Ultra is off. |
| Secure runtime | Future Contracts plus the semantic broker. OpenShell is the system boundary when `openshell-prover` is installed. It is not installed here, so the status stays `prover_unavailable`. OpenShell does not prove which calendar event may change. |
