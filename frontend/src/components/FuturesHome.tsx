import { useState } from "react";
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
  const [openId, setOpenId] = useState<string | null>(null);
  if (!futures.length && !conflicts.length) return null;
  const selected = conflicts.find((item) => (item.conflict_id ?? item.future_ids.join("-")) === openId) ?? null;
  return (
    <section className="mb-6" aria-label="Your futures">
      {futures.length ? (
        <>
          <p className="text-[11px] uppercase tracking-[0.16em] text-mute">Your futures</p>
          <ul className="mt-2 flex gap-2 overflow-x-auto">
            {futures.map((future) => (
              <li key={future.future_id}>
                <button
                  type="button"
                  className="min-w-44 rounded-card border border-white/10 bg-elevated px-3 py-2 text-left"
                  onClick={() => onOpen(future.plan_id)}
                >
                  <span className="block truncate text-sm text-paper">{future.name}</span>
                  <span className="mt-1 block text-[11px] uppercase tracking-[0.14em] text-tide">{future.status}</span>
                  <span className="mt-1 block text-xs text-mute">
                    {future.material_unknowns} material unknown{future.material_unknowns === 1 ? "" : "s"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {conflicts.length ? (
        <div className="mt-3">
          <button
            type="button"
            className="text-sm text-clay"
            onClick={() => {
              const first = conflicts[0];
              setOpenId(first.conflict_id ?? first.future_ids.join("-"));
            }}
          >
            {conflicts.length} cross-plan conflict{conflicts.length === 1 ? "" : "s"}
          </button>
          {selected ? <ConflictView conflict={selected} onClose={() => setOpenId(null)} /> : null}
        </div>
      ) : null}
    </section>
  );
}

function ConflictView({ conflict, onClose }: { conflict: CrossPlanConflict; onClose: () => void }) {
  const names = conflict.future_names ?? [];
  const resource = conflict.resource_id ?? conflict.shared_resource ?? "shared resource";
  const constraint = conflict.violated_constraint ?? conflict.constraint ?? "";
  return (
    <div className="mt-3 max-w-md rounded-card border border-white/10 bg-elevated p-4" aria-label="Cross-plan detail">
      <div className="text-sm text-paper">
        <p>{names[0] ?? conflict.future_ids[0]}</p>
        <p className="my-2 text-xs uppercase tracking-[0.14em] text-mute">{constraint}</p>
        <p>{names[1] ?? conflict.future_ids[1]}</p>
      </div>
      <p className="mt-3 text-sm text-paper">{conflict.description}</p>
      <p className="mt-2 text-xs text-mute">This plan works alone, but conflicts with another future.</p>
      <dl className="mt-3 space-y-1 text-xs text-mute">
        <div>Shared resource: {resource}</div>
        <div>Constraint: {constraint}</div>
        <div>Introduced by: {names[1] ?? conflict.future_ids[1]}</div>
        {conflict.repairable ? <div>Repair: choose one future, or move the overlapping window.</div> : null}
      </dl>
      <button type="button" className="mt-3 text-xs text-tide" onClick={onClose}>
        Close
      </button>
    </div>
  );
}
