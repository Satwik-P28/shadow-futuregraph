import { Check, Lock } from "lucide-react";
import type { PlanView } from "../api/types";
import { actionLabel, money, repairActions } from "./format";

export function ApprovalPanel({
  plan,
  repairId,
  busy,
  approved,
  onApprove,
}: {
  plan: PlanView;
  repairId: string | null;
  busy: boolean;
  approved: boolean;
  onApprove: () => void;
}) {
  if (approved) return null;
  const repair = plan.repairs.find((item) => item.id === repairId);
  const included = repairId ? repairActions(plan, repairId) : [];
  const held = (plan.graph?.nodes ?? []).filter((node) => node.type === "CONSTRAINT").slice(0, 4);
  return (
    <section className="rounded-card border border-white/10 bg-elevated p-4" aria-label="Approve this future">
      <h2 className="text-xl text-paper">Approve this future</h2>
      {repair ? <p className="mt-1 text-sm text-mute">{repair.label} · {money(repair.additional_cost)}</p> : null}
      {included.length ? (
        <div className="mt-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-mute">This repair would change</p>
          <ul className="mt-2 space-y-1">
            {included.map((label) => (
              <li key={label} className="flex items-start gap-2 text-sm text-paper">
                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-moss" aria-hidden />
                {label}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {held.length ? (
        <div className="mt-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-mute">Constraints that still apply</p>
          <ul className="mt-2 space-y-1">
            {held.map((node) => (
              <li key={node.id} className="flex items-start gap-2 text-sm text-mute">
                <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-mute" aria-hidden />
                {node.label}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {plan.contract?.forbidden_actions?.length ? (
        <ul className="mt-3 space-y-1">
          {plan.contract.forbidden_actions.slice(0, 4).map((id) => (
            <li key={id} className="text-xs text-mute">{actionLabel(plan, id)}</li>
          ))}
        </ul>
      ) : null}
      <button
        type="button"
        className="mt-4 w-full rounded-control bg-moss px-3 py-2.5 text-sm font-medium text-ink disabled:opacity-40"
        onClick={onApprove}
        disabled={!repairId || busy}
      >
        Approve future
      </button>
    </section>
  );
}
