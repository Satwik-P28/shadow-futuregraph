import { useEffect, useState } from "react";
import { analyzeFreeform, approveRepair, attemptAction, executePlan, injectEvent, loadBenchmark, loadEvents, loadPersonalStatus, loadPlan } from "./api/client";
import type { ConnectedTools, GraphNode, ModelabilityResult, PlanView, TraceEvent } from "./api/types";
import { Issues } from "./features/Issues";
import { FutureCanvas } from "./graph/FutureCanvas";

const TRIP = "Move my NYC trip to Friday and make sure everything still works.";
const MOVE = "I'm thinking about moving apartments next month. Does this plan actually work?";
const EXAMPLES = { travel: TRIP, apartment: MOVE } as const;
const SANDBOX_TOOLS: ConnectedTools = { calendar: "SANDBOX", mail: "SANDBOX", travel: "SANDBOX", search: "OFF" };

function watchLine(plan: PlanView | null): string {
  if (plan?.contract?.status === "STALE" || plan?.watch?.drift_status === "INVALID") {
    return "1 future needs attention";
  }
  if (plan?.watch?.monitoring) {
    const count = plan.watch.approved_futures;
    return count === 1 ? "Monitoring 1 approved future" : `Monitoring ${count} approved futures`;
  }
  return "No approved future being monitored";
}

export function App() {
  const [text, setText] = useState("");
  const [exampleId, setExampleId] = useState<"travel" | "apartment" | null>(null);
  const [tools, setTools] = useState<ConnectedTools>(SANDBOX_TOOLS);
  const [modelability, setModelability] = useState<ModelabilityResult | null>(null);
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

  useEffect(() => {
    void loadPersonalStatus()
      .then((status) => setTools(status.connected_tools))
      .catch(() => undefined);
  }, []);

  function loadExample(next: "travel" | "apartment") {
    setExampleId(next);
    setText(EXAMPLES[next]);
    setError("");
  }

  function editPlan(next: string) {
    setText(next);
    if (exampleId && next !== EXAMPLES[exampleId]) setExampleId(null);
  }

  async function analyzeCurrentPlan() {
    const current = text;
    if (!current.trim()) {
      setError("Enter what you are planning.");
      setPlan(null);
      setModelability(null);
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await analyzeFreeform(current, exampleId);
      setModelability(result.modelability);
      if (result.plan) {
        setPlan(result.plan);
        setRepairId(result.plan.recommended_repair_id);
        setApproved(false);
        setHighlight([]);
      } else {
        setPlan(null);
        setRepairId(null);
        setApproved(false);
      }
    } catch (err) {
      setPlan(null);
      setModelability(null);
      setError(err instanceof Error ? err.message : "The request failed.");
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
        <div className="flex flex-wrap items-center gap-2">
          {exampleId ? <p className="rounded-full border border-line px-3 py-1 text-xs text-clay">EXAMPLE CONTEXT</p> : null}
          <p className="rounded-full border border-line px-3 py-1 text-xs text-clay">{plan?.provider_mode ?? "SANDBOX"}</p>
        </div>
      </header>

      <section className="mt-6 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div>
          <label htmlFor="plan" className="text-sm text-mute">What are you planning?</label>
          <textarea
            id="plan"
            value={text}
            onChange={(event) => editPlan(event.target.value)}
            placeholder="Describe the plan you want checked."
            className="mt-2 h-36 w-full rounded-lg border border-line bg-panel p-3 text-paper"
          />
          <button type="button" className="mt-3 rounded-md bg-tide px-4 py-2 text-sm text-ink" onClick={() => void analyzeCurrentPlan()} disabled={busy}>
            Analyze my future
          </button>
          <div className="mt-4">
            <p className="text-xs uppercase tracking-[0.16em] text-mute">Try an example</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" className="rounded-full border border-line px-3 py-1 text-xs" onClick={() => loadExample("travel")}>
                NYC trip
              </button>
              <button type="button" className="rounded-full border border-line px-3 py-1 text-xs" onClick={() => loadExample("apartment")}>
                Apartment move
              </button>
            </div>
            {exampleId ? <p className="mt-2 text-xs text-mute">Example loaded. This uses a synthetic context, not a live account.</p> : null}
          </div>
          <div className="mt-4 text-xs text-mute" aria-label="Connected context">
            <p className="uppercase tracking-[0.16em]">Connected context</p>
            <p className="mt-1">Calendar: {tools.calendar} · Mail: {tools.mail} · Travel: {tools.travel} · Search: {tools.search}</p>
          </div>
          <div className="mt-3 text-xs" aria-label="Shadow Watch">
            <p className="uppercase tracking-[0.16em] text-mute">Shadow Watch</p>
            <p className="mt-1 text-paper">{watchLine(plan)}</p>
          </div>
          {busy ? <p className="mt-3 text-sm text-mute">Checking the future…</p> : null}
          {error ? <p className="mt-3 text-sm text-fault">{error}</p> : null}
          {modelability?.status === "NEEDS_INFORMATION" ? (
            <div className="mt-3" aria-label="Missing information">
              <p className="text-sm text-clay">I can model this plan, but I need {modelability.missing_information.length} things first:</p>
              <ul className="mt-2 list-disc pl-5 text-sm">
                {modelability.missing_information.map((item) => <li key={item}>{item}</li>)}
              </ul>
              <p className="mt-2 text-xs uppercase tracking-[0.16em] text-mute">Missing information</p>
            </div>
          ) : null}
          {modelability?.status === "UNSUPPORTED" ? (
            <div className="mt-3 text-sm text-clay">
              <p>{modelability.reason}</p>
              <p className="mt-2 text-mute">I can still help identify considerations, but I won't pretend to simulate it.</p>
            </div>
          ) : null}
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
          <p className="mt-2 font-serif text-2xl">{plan?.coverage?.summary ?? "Run a plan to see what could break, what is still unknown, and what Shadow can repair."}</p>
          {plan?.no_feasible_message ? <p className="mt-3 text-sm text-fault">{plan.no_feasible_message}</p> : null}
          {plan?.reconciliation ? (
            <p className={`mt-3 text-sm ${plan.reconciliation.matched ? "text-moss" : "text-fault"}`}>{plan.reconciliation.message}</p>
          ) : null}
          {plan?.memory ? (
            <p className="mt-3 text-sm text-paper">{plan.memory.label} <span className="text-mute">· {plan.memory.source}</span></p>
          ) : null}
          {plan?.watch?.message ? <p className="mt-3 text-sm text-clay">{plan.watch.message}</p> : null}
          {plan?.watch?.skill_name ? <p className="mt-1 text-xs text-mute">Reusable skill: {plan.watch.skill_name}</p> : null}
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
