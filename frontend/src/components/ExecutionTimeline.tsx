import type { PlanView, TraceEvent } from "../api/types";
import { actionLabel } from "./format";

export function ExecutionTimeline({
  plan,
  events,
  busy,
  onExecute,
  onBlock,
}: {
  plan: PlanView;
  events: TraceEvent[];
  busy: boolean;
  onExecute: () => void;
  onBlock: () => void;
}) {
  const executed = events.filter((event) => event.event_type === "ACTION_EXECUTED");
  return (
    <section aria-label="Execution">
      <h2 className="text-xl text-paper">Executing approved future</h2>
      {executed.length ? (
        <ol className="mt-3 space-y-2">
          {executed.map((event) => {
            const actionId = typeof event.payload.action_id === "string" ? event.payload.action_id : event.event_type;
            return (
              <li key={event.event_id} className="text-sm text-paper">✓ {actionLabel(plan, actionId)}</li>
            );
          })}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-mute">Nothing has been executed yet.</p>
      )}
      {plan.reconciliation ? (
        <p className={`mt-3 text-sm ${plan.reconciliation.matched ? "text-moss" : "text-fault"}`}>{plan.reconciliation.message}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="rounded-control border border-white/10 px-3 py-2 text-sm" onClick={onExecute} disabled={busy}>
          Execute sandbox actions
        </button>
        {plan.scenario_id === "travel" ? (
          <button type="button" className="rounded-control border border-white/10 px-3 py-2 text-sm" onClick={onBlock}>
            Try unrelated change
          </button>
        ) : null}
      </div>
    </section>
  );
}
