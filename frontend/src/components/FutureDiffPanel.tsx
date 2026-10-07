import type { PlanView } from "../api/types";

export function FutureDiffPanel({ plan }: { plan: PlanView }) {
  if (!plan.diff) return null;
  return (
    <section id="future-diff" aria-label="Future diff">
      <h2 className="text-xl text-paper">Future diff</h2>
      <p className="mt-1 text-xs text-mute">{plan.diff.before_label} → {plan.diff.after_label}</p>
      <ul className="mt-3 divide-y divide-white/10">
        {plan.diff.entries.map((entry) => (
          <li key={entry.id} className="grid grid-cols-[1fr_auto] items-baseline gap-3 py-2 text-sm">
            <span className="text-mute">{entry.label}</span>
            <span className="text-right text-paper">
              {entry.changed ? `${entry.before} → ${entry.after}` : "unchanged"}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-fault">{plan.diff.before_failure}</p>
      <p className="mt-1 text-xs text-moss">{plan.diff.after_failure}</p>
    </section>
  );
}
