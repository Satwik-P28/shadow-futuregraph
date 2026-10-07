import type { PlanView } from "../api/types";
import { money } from "./format";

export function RepairPanel({
  plan,
  repairId,
  onSelect,
  onDiff,
}: {
  plan: PlanView;
  repairId: string | null;
  onSelect: (id: string) => void;
  onDiff: () => void;
}) {
  const selected = plan.repairs.find((item) => item.id === repairId) ?? plan.repairs.find((item) => item.recommended);
  return (
    <section aria-label="Repairs">
      <h2 className="text-xl text-paper">Repairs</h2>
      {selected?.feasible ? (
        <div className="mt-3">
          <p className="text-[11px] uppercase tracking-[0.16em] text-moss">Recommended repair</p>
          <p className="mt-1 text-base text-paper">{selected.label}</p>
          <p className="mt-1 text-sm text-mute">
            {money(selected.additional_cost)} · {selected.changed_items} changed · {selected.failure_radius_label}
          </p>
          <button type="button" className="mt-2 text-sm text-tide" onClick={onDiff}>View future diff</button>
        </div>
      ) : null}
      <ul className="mt-3 space-y-2">
        {plan.repairs.map((repair) => (
          <li key={repair.id}>
            <button
              type="button"
              className={`w-full rounded-card border px-3 py-3 text-left ${repairId === repair.id ? "border-tide/70" : "border-white/10"} ${repair.feasible ? "bg-surface" : "bg-ink/30 opacity-70"}`}
              onClick={() => onSelect(repair.id)}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="text-sm text-paper">{repair.label}</span>
                {repair.recommended ? <span className="text-[11px] uppercase tracking-[0.14em] text-moss">Recommended</span> : null}
              </span>
              <span className="mt-1 block text-xs text-mute">
                {money(repair.additional_cost)} · {repair.changed_items} changed · {repair.failure_radius_label}
              </span>
              <span className="mt-1 block text-xs text-mute">
                {repair.status}{repair.feasible ? "" : " · Infeasible"} · {repair.failures.length} discovered failures
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
