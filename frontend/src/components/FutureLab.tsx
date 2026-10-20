import { useEffect, useState } from "react";
import { loadLab, nearestLab, simulateLab, type LabResult, type LabVariable } from "../api/client";

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

  async function apply(next: Record<string, number>, nearest = false) {
    const body = nearest ? await nearestLab(planId, pathId) : await simulateLab(planId, next, pathId);
    setValues((current) => ({ ...current, ...body.overrides }));
    setResult(body);
    onHighlight(body.highlight);
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
