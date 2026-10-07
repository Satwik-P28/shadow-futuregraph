import type { CrossPlanConflict, FutureCard } from "../api/client";

export function FuturesHome({
  futures,
  conflicts,
  onOpen,
}: {
  futures: FutureCard[];
  conflicts: CrossPlanConflict[];
  onOpen: (planId: string) => void;
}) {
  if (!futures.length && !conflicts.length) return null;
  return (
    <section className="mb-6" aria-label="Your futures">
      {futures.length ? (
        <>
          <p className="text-[11px] uppercase tracking-[0.16em] text-mute">Your futures</p>
          <ul className="mt-2 flex gap-2 overflow-x-auto">
            {futures.map((future) => (
              <li key={future.future_id}>
                <button type="button" className="min-w-44 rounded-card border border-white/10 bg-elevated px-3 py-2 text-left" onClick={() => onOpen(future.plan_id)}>
                  <span className="block truncate text-sm text-paper">{future.name}</span>
                  <span className="mt-1 block text-[11px] uppercase tracking-[0.14em] text-tide">{future.status}</span>
                  <span className="mt-1 block text-xs text-mute">{future.material_unknowns} material unknown{future.material_unknowns === 1 ? "" : "s"}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {conflicts.length ? (
        <div className="mt-3" aria-label="Cross-plan conflict">
          <p className="text-sm text-clay">Cross-plan conflict</p>
          <ul className="mt-1 space-y-1 text-xs text-mute">
            {conflicts.map((conflict) => (
              <li key={`${conflict.future_ids.join("-")}:${conflict.shared_resource}`}>
                {conflict.shared_resource}: {conflict.constraint}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
