import type { GraphNode, PlanView } from "../api/types";

const WHY: Record<string, string> = {
  FAILURE: "This branch is a discovered way the current plan breaks.",
  REPAIR: "This is a candidate change Shadow can test against the constraints.",
  CONSTRAINT: "This is a limit the future has to satisfy.",
  UNKNOWN: "Shadow does not have a grounded value for this yet.",
  ACTION: "This is an action inside a candidate future.",
  OUTCOME: "This is where the selected future lands.",
  EXOGENOUS_EVENT: "This is an outside change the plan does not control.",
};

export function EvidenceDrawer({ plan, node, onClose }: { plan: PlanView; node: GraphNode; onClose: () => void }) {
  const related = new Set<string>();
  for (const edge of plan.graph?.edges ?? []) {
    if (edge.source === node.id) related.add(edge.target);
    if (edge.target === node.id) related.add(edge.source);
  }
  const labels = (plan.graph?.nodes ?? []).filter((item) => related.has(item.id)).map((item) => item.label);
  return (
    <aside className="rounded-card border border-white/10 bg-elevated p-4" aria-label="Evidence">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-lg text-paper">{node.label}</h2>
        <button type="button" className="text-xs text-mute" onClick={onClose}>Close</button>
      </div>
      <p className="mt-2 text-[11px] uppercase tracking-[0.14em] text-tide">{node.epistemic_status}</p>
      <p className="mt-3 text-sm text-paper"><span className="text-mute">Source · </span>{node.provenance}</p>
      <p className="mt-2 text-sm text-mute">{WHY[node.type] ?? "This sits on a path to a constraint, failure, or outcome."}</p>
      {labels.length ? (
        <p className="mt-3 text-sm text-paper"><span className="text-mute">Connected to · </span>{labels.slice(0, 4).join(", ")}</p>
      ) : null}
    </aside>
  );
}
