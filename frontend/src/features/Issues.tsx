import type { Failure } from "../api/types";

export function bugCount(failures: Failure[]): number {
  return failures.length;
}

export function Issues({
  failures,
  canRepair = false,
  labelFor = (id: string) => id,
  onSelect,
}: {
  failures: Failure[];
  canRepair?: boolean;
  labelFor?: (id: string) => string;
  onSelect: (failure: Failure) => void;
}) {
  const count = bugCount(failures);
  return (
    <section aria-label="Future bugs">
      <h2 className="text-xl text-paper">
        {count === 1 ? "1 future bug found" : `${count} future bugs found`}
      </h2>
      <ul className="mt-3 space-y-2">
        {failures.map((failure, index) => {
          const trigger = failure.perturbations.map((item) => item.label).join(" + ");
          return (
            <li key={failure.id}>
              <button
                type="button"
                className="w-full rounded-card border border-white/10 bg-ink/40 px-3 py-3 text-left"
                onClick={() => onSelect(failure)}
              >
                <span className="text-[11px] tracking-[0.14em] text-fault">{String(index + 1).padStart(2, "0")}</span>
                <span className="mt-1 block text-sm text-paper">{failure.violated_constraints.map(labelFor).join(", ")}</span>
                {trigger ? <span className="mt-2 block text-xs text-mute">Trigger · {trigger}</span> : null}
                <span className="mt-1 block text-xs text-mute">
                  Nearest discovered failure · distance {failure.normalized_distance.toFixed(2)}
                </span>
                <span className="mt-1 block text-xs text-paper">{failure.causal_trace.join(" → ")}</span>
                {canRepair ? <span className="mt-2 block text-[11px] uppercase tracking-[0.14em] text-moss">Repairable</span> : null}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
