import { Activity } from "lucide-react";
import type { PlanView } from "../api/types";

export function watchLine(plan: PlanView | null): string {
  if (plan?.contract?.status === "STALE" || plan?.watch?.drift_status === "INVALID") {
    return "1 future needs attention";
  }
  if (plan?.watch?.monitoring) {
    const count = plan.watch.approved_futures;
    return count === 1 ? "Monitoring 1 approved future" : `Monitoring ${count} approved futures`;
  }
  return "No approved future being monitored";
}

export function ShadowWatch({ plan }: { plan: PlanView | null }) {
  const watching = Boolean(plan?.watch?.monitoring) && plan?.contract?.status !== "STALE" && plan?.watch?.drift_status !== "INVALID";
  return (
    <section aria-label="Shadow Watch">
      <div className="flex items-center gap-2">
        <Activity className="h-3.5 w-3.5 text-mute" aria-hidden />
        <p className="text-[11px] uppercase tracking-[0.16em] text-mute">Shadow Watch</p>
        {watching ? <span className="watch-dot" aria-hidden /> : null}
      </div>
      <p className="mt-1.5 text-sm text-paper">{watchLine(plan)}</p>
      {plan?.watch?.message ? <p className="mt-1 text-sm text-clay">{plan.watch.message}</p> : null}
      {plan?.watch?.skill_name ? <p className="mt-1 text-xs text-mute">Reusable skill: {plan.watch.skill_name}</p> : null}
      {plan?.memory ? (
        <p className="mt-2 text-sm text-paper">{plan.memory.label} <span className="text-mute">· {plan.memory.source}</span></p>
      ) : null}
    </section>
  );
}
