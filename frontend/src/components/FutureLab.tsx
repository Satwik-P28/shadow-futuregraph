import { useEffect, useState } from "react";
import { batchLab, compareLab, ingestDeadline, loadLab, nearestLab, simulateLab, type BatchResult, type ComparisonResult, type LabResult, type LabVariable } from "../api/client";

export function FutureLab({
  planId,
  repairId,
  naiveRepairId,
  onHighlight,
}: {
  planId: string;
  repairId: string | null;
  naiveRepairId: string | null;
  onHighlight: (ids: string[]) => void;
}) {
  const [variables, setVariables] = useState<LabVariable[]>([]);
  const [values, setValues] = useState<Record<string, number>>({});
  const [result, setResult] = useState<LabResult | null>(null);
  const [batch, setBatch] = useState<BatchResult | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [deadlineResult, setDeadlineResult] = useState<Record<string, unknown> | null>(null);
  const [deadlineBusy, setDeadlineBusy] = useState(false);
  const [pathId, setPathId] = useState(repairId);

  useEffect(() => {
    let alive = true;
    void loadLab(planId).then((body) => {
      if (!alive) return;
      setVariables(body.variables);
      setValues(Object.fromEntries(body.variables.map((item) => [item.id, item.baseline])));
    }).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [planId]);

  useEffect(() => {
    setPathId(repairId);
  }, [repairId]);

  useEffect(() => {
    let alive = true;
    setBatchBusy(true);
    void batchLab(planId, pathId).then((body) => {
      if (alive) setBatch(body);
    }).catch(() => undefined).finally(() => {
      if (alive) setBatchBusy(false);
    });
    return () => {
      alive = false;
    };
  }, [planId, pathId]);

  useEffect(() => {
    void compareLab(planId).then(setComparison).catch(() => undefined);
  }, [planId, batch]);

  async function apply(next: Record<string, number>, nearest = false) {
    const body = nearest ? await nearestLab(planId, pathId) : await simulateLab(planId, next, pathId);
    setValues((current) => ({ ...current, ...body.overrides }));
    setResult(body);
    onHighlight(body.highlight);
  }

  async function runBatch() {
    setBatchBusy(true);
    try {
      setBatch(await batchLab(planId, pathId));
    } finally {
      setBatchBusy(false);
    }
  }

  async function submitConfirmation() {
    setDeadlineBusy(true);
    try {
      const response = await ingestDeadline(planId, confirmation);
      setDeadlineResult(response);
      if (response.status === "APPLIED") {
        setComparison((response.after as ComparisonResult) ?? null);
      }
    } finally {
      setDeadlineBusy(false);
    }
  }

  if (!variables.length) return null;
  const selectedVariables = variables.filter((item) => values[item.id] !== item.baseline);
  return (
    <section aria-label="Counterfactual future lab" className="rounded-card border border-white/10 bg-white/[0.02] p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-tide">Counterfactual exploration</p>
      <h2 className="mt-1 text-xl text-paper">Change one modeled uncertainty</h2>
      <p className="mt-1 text-xs leading-relaxed text-mute">Simulation. This does not change the approved future or execute anything. These controls are bounded by scenario data, and Shadow re-evaluates the selected future through the backend.</p>
      <div className="mt-3 space-y-3">
        {variables.map((item) => (
          <label key={item.id} className="block text-sm">
            <span className="flex justify-between text-paper">
              <span>{item.label}</span>
              <span className="text-mute">{Math.round(values[item.id] ?? item.baseline)} {item.unit} · {Math.round(item.lower)}–{Math.round(item.upper)}</span>
            </span>
            <input
              className="mt-1 w-full accent-tide"
              type="range"
              min={item.lower}
              max={item.upper}
              value={values[item.id] ?? item.baseline}
              aria-label={item.label}
              onChange={(event) => {
                const next = { ...values, [item.id]: Number(event.target.value) };
                setValues(next);
                void apply(next);
              }}
            />
          </label>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={`rounded-full border px-3 py-1 text-xs ${pathId === naiveRepairId ? "border-fault/60 text-fault" : "border-white/10 text-mute"}`} onClick={() => { setPathId(naiveRepairId); setResult(null); }}>
          Original intention
        </button>
        <button type="button" className={`rounded-full border px-3 py-1 text-xs ${pathId === repairId ? "border-moss/60 text-moss" : "border-white/10 text-mute"}`} onClick={() => { setPathId(repairId); setResult(null); }}>
          Recommended future
        </button>
      </div>
      <div className="mt-4 rounded-control border border-white/10 bg-black/10 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-[11px] uppercase tracking-[0.14em] text-tide">Bounded future sweep</p>
            <p className="mt-1 text-xs text-mute">Actual grid evaluation across the selected path; not probabilities.</p>
          </div>
          {comparison ? (
            <div className="mt-4 rounded-control border border-white/10 bg-black/10 p-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-tide">Compared futures</p>
              <p className="mt-1 text-xs text-mute">{comparison.evaluated_per_option} actual evaluations per supported option. {comparison.objective}.</p>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {comparison.options.map((option) => (
                  <div key={option.id} className={`rounded-control border p-3 ${option.recommended ? "border-moss/50" : "border-white/10"}`}>
                    <div className="flex justify-between gap-2">
                      <span className="text-sm text-paper">{option.label}</span>
                      {option.recommended ? <span className="text-xs text-moss">Selected</span> : null}
                    </div>
                    <p className="mt-1 text-xs text-mute">{option.feasible} feasible · {option.hard_constraint_failures} failing · margin {Math.round(option.worst_tested_constraint_margin)} · cost {option.cost}</p>
                    {option.representative_failures[0] ? <p className="mt-1 text-xs text-fault">{option.representative_failures[0].violated_labels.join("; ")}</p> : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          <div className="mt-4 rounded-control border border-white/10 bg-black/10 p-3">
            <p className="text-[11px] uppercase tracking-[0.14em] text-tide">Grounded deadline update</p>
            <p className="mt-1 text-xs text-mute">Paste a supported event confirmation. Nemotron must quote it before Shadow changes the modeled deadline.</p>
            <textarea className="mt-2 min-h-20 w-full rounded-control border border-white/10 bg-black/20 p-2 text-xs text-paper" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder="Reservation confirmation: guests must arrive by 6:30 PM." />
            <button type="button" className="mt-2 rounded-control border border-tide/40 px-3 py-1.5 text-xs text-tide" disabled={!confirmation.trim() || deadlineBusy} onClick={() => void submitConfirmation()}>{deadlineBusy ? "Updating future…" : "Update future from confirmation"}</button>
            {deadlineResult ? <p className={`mt-2 text-xs ${deadlineResult.status === "APPLIED" ? "text-moss" : "text-fault"}`}>{String(deadlineResult.status)}: {String(deadlineResult.reason ?? (deadlineResult.fact as { quote?: string })?.quote ?? "comparison updated")}</p> : null}
          </div>
          <button type="button" className="rounded-control border border-tide/40 px-3 py-1.5 text-xs text-tide" onClick={() => void runBatch()} disabled={batchBusy}>
            {batchBusy ? "Evaluating…" : "Evaluate futures"}
          </button>
        </div>
        {batch ? (
          <div className="mt-3">
            <p className="text-lg text-paper">{batch.evaluated} futures evaluated</p>
            <p className="mt-1 text-xs text-mute">{batch.feasible} feasible · {batch.failing} failing · variables: {batch.variables.join(", ")}</p>
            {batch.representative_failures[0] ? (
              <p className="mt-2 text-xs text-fault">Failure example: {batch.representative_failures[0].violated_labels.join("; ")}</p>
            ) : null}
          </div>
        ) : null}
      </div>
      <p className="mt-3 text-xs text-mute">
        Evaluating: {pathId ?? "original intention"} · {selectedVariables.length ? selectedVariables.map((item) => item.label).join(", ") : "baseline"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="rounded-control border border-white/10 px-3 py-1.5 text-xs" onClick={() => void apply(values, true)}>
          Find nearest failure
        </button>
        <button
          type="button"
          className="rounded-control border border-white/10 px-3 py-1.5 text-xs"
          onClick={() => {
            const baseline = Object.fromEntries(variables.map((item) => [item.id, item.baseline]));
            setValues(baseline);
            setResult(null);
            onHighlight([]);
          }}
        >
          Return to approved state
        </button>
      </div>
      {result ? (
        <div className={`mt-3 rounded-control border p-3 ${result.holds ? "border-moss/30 bg-moss/5" : "border-fault/40 bg-fault/5"}`}>
          <p className={`text-sm ${result.holds ? "text-moss" : "text-fault"}`}>{result.holds ? "Evaluated path holds" : "Evaluated path fails"}</p>
          <p className="mt-1 text-sm text-paper">{result.message}</p>
          {!result.holds && result.violated_labels.length ? (
            <p className="mt-2 text-xs text-fault">Violated: {result.violated_labels.join("; ")}</p>
          ) : null}
          {result.perturbations?.length ? (
            <ul className="mt-2 space-y-1 text-xs text-mute">
              {result.perturbations.map((item) => <li key={item.variable}>{item.label}: {Math.round(item.baseline)} → {Math.round(item.value)} {variables.find((control) => control.id === item.variable)?.unit}</li>)}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
