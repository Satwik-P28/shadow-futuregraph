import { useEffect, useState } from "react";
import { analyzeFreeform, approveRepair, attemptAction, executePlan, injectEvent, loadBenchmark, loadEvents, loadFutures, loadPersonalStatus, loadPlan, resetDemo, type CrossPlanConflict, type FutureCard } from "./api/client";
import type { ConnectedTools, GraphNode, ModelabilityResult, PlanView, TraceEvent } from "./api/types";
import { DecisionTrace } from "./components/DecisionTrace";
import { EvaluationPanel, formatBenchmark } from "./components/EvaluationPanel";
import { FutureEmptyState } from "./components/FutureEmptyState";
import { FuturesHome } from "./components/FuturesHome";
import { FutureWorkspace } from "./components/FutureWorkspace";
import { GraphSkeleton } from "./components/AnalysisProgress";
import { EXAMPLES, HeroPlanInput } from "./components/HeroPlanInput";
import { ShadowWatch } from "./components/ShadowWatch";

const SANDBOX_TOOLS: ConnectedTools = { calendar: "SANDBOX", mail: "SANDBOX", travel: "SANDBOX", search: "OFF" };

export function App() {
  const [text, setText] = useState("");
  const [exampleId, setExampleId] = useState<"travel" | "apartment" | null>(null);
  const [tools, setTools] = useState<ConnectedTools>(SANDBOX_TOOLS);
  const [modelability, setModelability] = useState<ModelabilityResult | null>(null);
  const [plan, setPlan] = useState<PlanView | null>(null);
  const [workspace, setWorkspace] = useState(false);
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
  const [showEval, setShowEval] = useState(false);
  const [bench, setBench] = useState("");
  const [pulseToken, setPulseToken] = useState(0);
  const [futures, setFutures] = useState<FutureCard[]>([]);
  const [conflicts, setConflicts] = useState<CrossPlanConflict[]>([]);

  useEffect(() => {
    void loadPersonalStatus()
      .then((status) => setTools(status.connected_tools))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    void loadFutures()
      .then((body) => {
        setFutures(body.futures);
        setConflicts(body.conflicts);
      })
      .catch(() => undefined);
  }, [plan?.id, plan?.status]);

  function loadExample(next: "travel" | "apartment") {
    setExampleId(next);
    setText(EXAMPLES[next]);
    setError("");
  }

  function editPlan(next: string) {
    setText(next);
    if (exampleId && next !== EXAMPLES[exampleId]) setExampleId(null);
  }

  async function restoreDemo() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const view = await resetDemo();
      setPlan(view);
      setText(view.text);
      setRepairId(view.recommended_repair_id);
      setWorkspace(Boolean(view.graph));
      setExampleId("travel");
      const body = await loadFutures();
      setFutures(body.futures);
      setConflicts(body.conflicts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setBusy(false);
    }
  }

  async function analyzeCurrentPlan() {
    const current = text;
    if (!current.trim()) {
      setError("Enter what you are planning.");
      setPlan(null);
      setModelability(null);
      setWorkspace(false);
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    setWorkspace(false);
    try {
      const result = await analyzeFreeform(current, exampleId);
      setModelability(result.modelability);
      if (result.plan?.graph) {
        setPlan(result.plan);
        setRepairId(result.plan.recommended_repair_id);
        setApproved(false);
        setHighlight([]);
        setSelected(null);
        setWorkspace(true);
      } else {
        setPlan(result.plan);
        setRepairId(null);
        setApproved(false);
        setWorkspace(false);
      }
    } catch (err) {
      setPlan(null);
      setModelability(null);
      setWorkspace(false);
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
    setPulseToken((value) => value + 1);
  }

  async function toggleTrace() {
    const next = !showTrace;
    setShowTrace(next);
    if (next && plan) {
      try {
        setEvents(await loadEvents(plan.id));
      } catch {
        setEvents([]);
      }
    }
  }

  async function toggleEval() {
    const next = !showEval;
    setShowEval(next);
    if (!next || bench) return;
    const body = await loadBenchmark();
    if (!body.available || !body.summary) {
      setBench("No local ShadowBench summary is checked in.");
      return;
    }
    setBench(formatBenchmark(body.summary as Parameters<typeof formatBenchmark>[0]));
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-[1200px] flex-col px-5 py-4 md:px-8">
      <header className="mb-6 flex items-center justify-between gap-4">
        <p className="text-[11px] uppercase tracking-[0.22em] text-tide">Shadow</p>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {exampleId ? <p className="rounded-full border border-white/10 px-3 py-1 text-[11px] tracking-[0.12em] text-clay">EXAMPLE CONTEXT</p> : null}
          <button type="button" className="text-[11px] tracking-[0.12em] text-mute" onClick={() => void restoreDemo()}>
            Reset demo
          </button>
          <p className="rounded-full border border-white/10 px-3 py-1 text-[11px] tracking-[0.12em] text-clay">{plan?.provider_mode ?? "SANDBOX"}</p>
        </div>
      </header>
      <FuturesHome
        futures={futures}
        conflicts={conflicts}
        onOpen={(id) => {
          if (!id || id.startsWith("demo-")) return;
          void loadPlan(id).then((view) => {
            setPlan(view);
            setText(view.text);
            setRepairId(view.recommended_repair_id);
            setWorkspace(Boolean(view.graph));
          });
        }}
      />

      {workspace && plan?.graph ? (
        <FutureWorkspace
          plan={plan}
          tools={tools}
          repairId={repairId}
          approved={approved}
          busy={busy}
          expanded={expanded}
          highlight={highlight}
          selected={selected}
          notice={notice}
          events={events}
          pulseToken={pulseToken}
          onBack={() => setWorkspace(false)}
          onExpand={() => setExpanded((value) => !value)}
          onSelectNode={setSelected}
          onSelectFailure={(_id, constraint, variables) => setHighlight([`con:${constraint}`, ...variables.map((item) => `var:${item}`)])}
          onSelectRepair={setRepairId}
          onHighlight={setHighlight}
          onApprove={() => void approve()}
          onExecute={() => void execute()}
          onBlock={() => void blockUnrelated()}
          onInject={(eventId) => void inject(eventId)}
        />
      ) : (
        <section className="grid flex-1 items-center gap-10 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.9fr)]">
          <div>
            <HeroPlanInput
              text={text}
              exampleId={exampleId}
              tools={tools}
              busy={busy}
              error={error}
              modelability={modelability}
              onEdit={editPlan}
              onAnalyze={() => void analyzeCurrentPlan()}
              onExample={loadExample}
            />
            <div className="mt-6">
              <ShadowWatch plan={plan} />
            </div>
          </div>
          <div>{busy ? <GraphSkeleton /> : <FutureEmptyState />}</div>
        </section>
      )}

      {error && workspace ? <p className="mt-4 text-sm text-fault">{error}</p> : null}

      <footer className="mt-8 flex flex-wrap gap-8 border-t border-white/10 pt-4">
        <EvaluationPanel open={showEval} summary={bench} onToggle={() => void toggleEval()} />
        <DecisionTrace open={showTrace} events={events} onToggle={() => void toggleTrace()} />
      </footer>
    </main>
  );
}
