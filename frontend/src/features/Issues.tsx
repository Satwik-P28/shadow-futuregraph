import type { Failure } from "../api/types";

export function bugCount(failures: Failure[]): number {
  return failures.length;
}

export function Issues({ failures, onSelect }: { failures: Failure[]; onSelect: (failure: Failure) => void }) {
  return (
    <section aria-label="Future bugs">
      <h2 className="font-serif text-2xl text-paper">
        {bugCount(failures) === 1 ? "1 future bug found" : `${bugCount(failures)} future bugs found`}
      </h2>
      <ul className="mt-3 space-y-2">
        {failures.map((failure) => (
          <li key={failure.id}>
            <button
              type="button"
              className="w-full rounded-md border border-line bg-ink px-3 py-2 text-left"
              onClick={() => onSelect(failure)}
            >
              <span className="block text-sm text-fault">{failure.violated_constraints.join(", ")}</span>
              <span className="mt-1 block text-xs text-mute">
                Nearest discovered failure · distance {failure.normalized_distance.toFixed(2)}
              </span>
              <span className="mt-1 block text-xs text-paper">{failure.causal_trace.join(" → ")}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
