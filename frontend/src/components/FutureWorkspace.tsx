import type { ConnectedTools, GraphNode, PlanView, TraceEvent } from "../api/types";
import { Issues } from "../features/Issues";
import { FutureCanvas } from "../graph/FutureCanvas";
import { ApprovalPanel } from "./ApprovalPanel";
import { STAGE_LABELS } from "./format";
import { ConnectedContext } from "./ConnectedContext";
import { DemoControls } from "./DemoControls";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { ExecutionTimeline } from "./ExecutionTimeline";
import { FutureDiffPanel } from "./FutureDiffPanel";
import { RepairPanel } from "./RepairPanel";
import { ShadowWatch } from "./ShadowWatch";

export function FutureWorkspace({
  plan,
  tools,
  repairId,
  approved,
  busy,
  expanded,
  highlight,
  selected,
  notice,
  events,
  pulseToken,
  onBack,
  onExpand,
  onSelectNode,
  onSelectFailure,
  onSelectRepair,
  onApprove,
  onExecute,
  onBlock,
  onInject,
}: {
  plan: PlanView;
  tools: ConnectedTools;
  repairId: string | null;
  approved: boolean;
  busy: boolean;
  expanded: boolean;
  highlight: string[];
  selected: GraphNode | null;
  notice: string;
  events: TraceEvent[];
  pulseToken: number;
  onBack: () => void;
  onExpand: () => void;
  onSelectNode: (node: GraphNode | null) => void;
  onSelectFailure: (failureId: string, constraint: string, variables: string[]) => void;
  onSelectRepair: (id: string) => void;
  onApprove: () => void;
  onExecute: () => void;
  onBlock: () => void;
  onInject: (eventId: string) => void;
}) {
  const nearest = plan.failures[0];
  const trigger = nearest?.perturbations.map((item) => item.label).join(" + ");
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-4">
        <div className="min-w-0">
          <button type="button" className="text-xs text-mute" onClick={onBack}>← Plan</button>
          <p className="mt-1 max-w-2xl truncate text-sm text-paper">{plan.text}</p>
        </div>
        <ConnectedContext tools={tools} />
      </div>
      <div className="mt-5 grid items-start gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.85fr)]">
        <div className="min-w-0">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-[22px] text-paper">Future graph</h2>
            <button type="button" className="rounded-control border border-white/10 px-3 py-1 text-xs" onClick={onExpand}>
              {expanded ? "Collapse detail" : "Expand detail"}
            </button>
          </div>
          <FutureCanvas
            nodes={plan.graph?.nodes ?? []}
            edges={plan.graph?.edges ?? []}
            expanded={expanded}
            highlight={highlight}
            repairId={repairId}
            approved={approved}
            pulseToken={pulseToken}
            onSelect={onSelectNode}
          />
          {plan.compiled_from ? (
            <p className="mt-3 text-xs text-mute">Compiled from {plan.compiled_from}. The model may structure the problem. Shadow does not treat that structure as proof.</p>
          ) : null}
          <p className="mt-1 text-xs text-mute">
            {plan.stages.map((stage) => STAGE_LABELS[stage.name] ?? stage.name).join(" · ")} · {plan.observability.worlds_simulated} worlds · {plan.observability.model_calls} model calls
          </p>
          {selected ? (
            <div className="mt-4">
              <EvidenceDrawer plan={plan} node={selected} onClose={() => onSelectNode(null)} />
            </div>
          ) : null}
        </div>
        <aside className="space-y-8">
          <section>
            <p className="text-[11px] uppercase tracking-[0.16em] text-mute">Future status</p>
            {trigger ? <p className="mt-2 text-sm text-paper">Nearest failure · {trigger}</p> : null}
            {plan.coverage ? <p className="mt-1 text-sm text-mute">Material unknowns · {plan.coverage.unknown}</p> : null}
            {plan.coverage?.summary ? <p className="mt-1 text-xs text-mute">{plan.coverage.summary}</p> : null}
            {plan.no_feasible_message ? <p className="mt-2 text-sm text-fault">{plan.no_feasible_message}</p> : null}
          </section>
          <Issues
            failures={plan.failures}
            canRepair={plan.repairs.some((repair) => repair.feasible)}
            labelFor={(id) => plan.graph?.nodes.find((node) => node.id === `con:${id}`)?.label ?? id}
            onSelect={(failure) => onSelectFailure(failure.id, failure.violated_constraints[0] ?? "", failure.perturbations.map((item) => item.variable))}
          />
          <RepairPanel plan={plan} repairId={repairId} onSelect={onSelectRepair} onDiff={() => document.getElementById("future-diff")?.scrollIntoView({ block: "nearest" })} />
          <FutureDiffPanel plan={plan} />
          {approved ? (
            <ExecutionTimeline plan={plan} events={events} busy={busy} onExecute={onExecute} onBlock={onBlock} />
          ) : (
            <ApprovalPanel plan={plan} repairId={repairId} busy={busy} approved={approved} onApprove={onApprove} />
          )}
          <ShadowWatch plan={plan} />
          {notice ? <p className="text-sm text-clay">{notice}</p> : null}
          {plan.scenario_id === "travel" && (plan.provider_mode === "SANDBOX" || !plan.provider_mode) ? (
            <DemoControls onInject={onInject} />
          ) : null}
        </aside>
      </div>
    </div>
  );
}
