import { useEffect, useState } from "react";
import { loadLab, nearestLab, simulateLab, type LabResult, type LabVariable } from "../api/client";

export function FutureLab({
  planId,
  repairId,
  onHighlight,
}: {
  planId: string;
  repairId: string | null;
  onHighlight: (ids: string[]) => void;
}) {
  const [variables, setVariables] = useState<LabVariable[]>([]);
  const [values, setValues] = useState<Record<string, number>>({});
  const [result, setResult] = useState<LabResult | null>(null);

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

  async function apply(next: Record<string, number>, nearest = false) {
    const body = nearest ? await nearestLab(planId, repairId) : await simulateLab(planId, next, repairId);
    setValues((current) => ({ ...current, ...body.overrides }));
    setResult(body);
    onHighlight(body.highlight);
  }

  if (!variables.length) return null;
  return (
    <section aria-label="Future lab">
      <h2 className="text-xl text-paper">Future lab</h2>
      <p className="mt-1 text-xs text-mute">Simulation. This does not change the approved future or execute anything.</p>
      <div className="mt-3 space-y-3">
        {variables.map((item) => (
          <label key={item.id} className="block text-sm">
            <span className="flex justify-between text-paper">
              <span>{item.label}</span>
              <span className="text-mute">{Math.round(values[item.id] ?? item.baseline)}{item.unit}</span>
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
      {result ? <p className={`mt-3 text-sm ${result.holds ? "text-moss" : "text-fault"}`}>{result.message}</p> : null}
    </section>
  );
}
