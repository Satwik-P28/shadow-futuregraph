import { useState } from "react";
import { analyzePlan, approveRepair, attemptAction, createPlan, executePlan, injectEvent, loadBenchmark, loadEvents, loadPlan } from "./api/client";
import type { GraphNode, PlanView, TraceEvent } from "./api/types";
import { Issues } from "./features/Issues";
import { FutureCanvas } from "./graph/FutureCanvas";

const TRIP = "Move my NYC trip to Friday and make sure everything still works.";
const MOVE = "I'm thinking about moving apartments next month. Does this plan actually work?";

export function App() {
  const [text, setText] = useState(TRIP);
  const [plan, setPlan] = useState<PlanView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [highlight, setHighlight] = useState<string[]>([]);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [repairId, setRepairId] = useState<string | null>(null);
  const [approved, setApproved] = useState(false);
  const [notice, setNotice] = useState("");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [showTrace, setShowTrace] = useState(false);
  const [bench, setBench] = useState<string>("");

  async function run(scenarioId: string, prompt: string) {
    setBusy(true);
    setError("");
    setNotice("");
    setText(prompt);
    try {
      const created = await createPlan(prompt, scenarioId);
      const view = await analyzePlan(created.id);
      setPlan(view);
      setRepairId(view.recommended_repair_id);
      setApproved(false);
      setHighlight([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "analysis failed");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!plan || !repairId) return;
    setBusy(true);
    try {
      await approveRepair(plan.id, repairId);
      setPlan(await loadPlan(plan.id));
      setApproved(true);
      setNotice("Repaired future approved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "approval failed");
    } finally {
      setBusy(false);
    }
  }

  async function execute() {
    if (!plan) return;
    setBusy(true);
    try {
      await executePlan(plan.id);
      setPlan(await loadPlan(plan.id));
      setEvents(await loadEvents(plan.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "execution failed");
    } finally {
      setBusy(false);
    }
  }

  async function blockUnrelated() {
    if (!plan) return;
    const result = await attemptAction(plan.id, "update_exam");
    setNotice(result.message);
    setEvents(await loadEvents(plan.id));
  }

  async function inject(eventId: string) {
    if (!plan) return;
    const result = await injectEvent(plan.id, eventId);
    setNotice(result.message);
    setPlan(await loadPlan(plan.id));
  }

  const graphNodes = plan?.graph?.nodes ?? [];
  const shownFailures = plan?.failures ?? [];

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-tide">Shadow</p>
          <h1 className="font-serif text-4xl text-paper">Find bugs in your future before you commit to it.</h1>
        </div>
        <p className="rounded-full border border-line px-3 py-1 text-xs text-clay">{plan?.provider_mode ?? "SANDBOX"}</p>
      </header>

      <section className="mt-6 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div>
          <label htmlFor="plan" className="text-sm text-mute">What are you planning?</label>
          <textarea
            id="plan"
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="mt-2 h-28 w-full rounded-lg border border-line bg-panel p-3 text-paper"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="rounded-md bg-tide px-3 py-2 text-sm text-ink" onClick={() => run("travel", TRIP)} disabled={busy}>
              Check the Friday trip
            </button>
            <button type="button" className="rounded-md border border-line px-3 py-2 text-sm" onClick={() => run("apartment", MOVE)} disabled={busy}>
              Check the apartment move
            </button>
          </div>
          {busy ? <p className="mt-3 text-sm text-mute">Checking the future…</p> : null}
          {error ? <p className="mt-3 text-sm text-fault">{error}</p> : null}
          {plan?.compiled_from ? (
            <p className="mt-3 text-sm text-mute">Compiled from {plan.compiled_from}. The model may structure the problem. Shadow does not treat that structure as proof.</p>
          ) : null}
          {plan ? (
            <p className="mt-3 text-xs text-mute">
              {plan.stages.map((stage) => stage.name).join(" · ")} · {plan.observability.worlds_simulated} worlds · {plan.observability.model_calls} model calls
            </p>
          ) : null}
        </div>
        <aside className="rounded-lg border border-line bg-panel p-4">
          <p className="text-sm text-mute">Modeled future coverage</p>
          <p className="mt-2 font-serif text-2xl">{plan?.coverage?.summary ?? "Run a plan to see what is still unknown."}</p>
          {plan?.no_feasible_message ? <p className="mt-3 text-sm text-fault">{plan.no_feasible_message}</p> : null}
          {plan?.reconciliation ? (
            <p className={`mt-3 text-sm ${plan.reconciliation.matched ? "text-moss" : "text-fault"}`}>{plan.reconciliation.message}</p>
          ) : null}
          {notice ? <p className="mt-3 text-sm text-clay">{notice}</p> : null}
        </aside>
      </section>

      {plan?.graph ? (
        <section className="mt-6 grid gap-4 lg:grid-cols-[1.4fr_0.8fr]">
          <div>
            <div className="mb-2 flex gap-2">
              <button type="button" className="rounded-md border border-line px-3 py-1 text-sm" onClick={() => setExpanded((value) => !value)}>
                {expanded ? "Collapse detail" : "Expand detail"}
              </button>
            </div>
            <FutureCanvas
              nodes={graphNodes}
              edges={plan.graph.edges}
              expanded={expanded}
              highlight={highlight}
              onSelect={setSelected}
            />
          </div>
          <div className="space-y-6">
            <Issues
              failures={shownFailures}
              onSelect={(failure) =>
                setHighlight([
                  `con:${failure.violated_constraints[0]}`,
                  ...failure.perturbations.map((item) => `var:${item.variable}`),
                ])
              }
            />
            <section aria-label="Repairs">
              <h2 className="font-serif text-2xl">Repairs</h2>
              <ul className="mt-3 space-y-2">
                {plan.repairs.map((repair) => (
                  <li key={repair.id}>
                    <button
                      type="button"
                      className={`w-full rounded-md border px-3 py-2 text-left ${repairId === repair.id ? "border-tide" : "border-line"}`}
                      onClick={() => setRepairId(repair.id)}
                    >
                      <span className="block text-sm">{repair.label}</span>
                      <span className="text-xs text-mute">
                        {repair.status} · {repair.failure_radius_label}
                        {repair.recommended ? " · recommended" : ""}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
            {plan.diff ? (
              <section aria-label="Future diff">
                <h2 className="font-serif text-2xl">Future diff</h2>
                <p className="mt-1 text-xs text-mute">{plan.diff.before_label} → {plan.diff.after_label}</p>
                <ul className="mt-2 space-y-1 text-sm">
                  {plan.diff.entries.map((entry) => (
                    <li key={entry.id}>
                      {entry.label}: {entry.changed ? `${entry.before} → ${entry.after}` : "unchanged"}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-fault">{plan.diff.before_failure}</p>
                <p className="text-xs text-moss">{plan.diff.after_failure}</p>
              </section>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button type="button" className="rounded-md bg-moss px-3 py-2 text-sm text-ink" onClick={approve} disabled={!repairId || busy}>
                Approve repaired future
              </button>
              <button type="button" className="rounded-md border border-line px-3 py-2 text-sm" onClick={execute} disabled={!approved || busy}>
                Execute sandbox actions
              </button>
              {plan.scenario_id === "travel" ? (
                <button type="button" className="rounded-md border border-line px-3 py-2 text-sm" onClick={blockUnrelated} disabled={!approved}>
                  Try unrelated change
                </button>
              ) : null}
            </div>
            {plan.scenario_id === "travel" ? (
              <div className="flex flex-wrap gap-2" aria-label="Inject world change">
                <button type="button" className="rounded-md border border-line px-3 py-2 text-sm" onClick={() => inject("delay_74")}>+74 min delay</button>
                <button type="button" className="rounded-md border border-line px-3 py-2 text-sm" onClick={() => inject("fare_increase")}>Fare +$80</button>
                <button type="button" className="rounded-md border border-line px-3 py-2 text-sm" onClick={() => inject("hotel_canceled")}>Hotel canceled</button>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {selected ? (
        <aside className="mt-4 rounded-lg border border-line bg-panel p-4" aria-label="Evidence">
          <h2 className="font-serif text-xl">{selected.label}</h2>
          <p className="mt-1 text-sm text-mute">{selected.epistemic_status} · {selected.provenance}</p>
          <p className="mt-2 text-sm">This node is material because it sits on a path to a constraint, failure, or outcome.</p>
        </aside>
      ) : null}

      <section className="mt-6" aria-label="ShadowBench">
        <button
          type="button"
          className="text-sm text-tide"
          onClick={async () => {
            const body = await loadBenchmark();
            if (!body.available) {
              setBench("No local ShadowBench summary is checked in.");
              return;
            }
            const systems = (body.summary as { systems: Record<string, { TaskCompletionRate: { count: number; n: number }; UndetectedFailureRate: { count: number; n: number } }> }).systems;
            setBench(
              Object.entries(systems)
                .map(([name, row]) => `${name}: completion ${row.TaskCompletionRate.count}/${row.TaskCompletionRate.n}, undetected ${row.UndetectedFailureRate.count}/${row.UndetectedFailureRate.n}`)
                .join(" · "),
            );
          }}
        >
          ShadowBench
        </button>
        {bench ? <p className="mt-2 text-xs text-mute">{bench}</p> : null}
      </section>

      <section className="mt-6">
        <button type="button" className="text-sm text-tide" onClick={() => setShowTrace((value) => !value)}>
          Decision trace
        </button>
        {showTrace ? (
          <ul className="mt-2 space-y-1 text-xs text-mute">
            {events.map((event) => (
              <li key={event.event_id}>{event.event_type}</li>
            ))}
          </ul>
        ) : null}
      </section>
    </main>
  );
}
