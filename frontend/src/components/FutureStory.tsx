import type { PlanView } from "../api/types";

export function FutureStory({ plan }: { plan: PlanView }) {
  const failures = plan.failures.length;
  const alternatives = plan.repairs.filter((repair) => repair.id !== plan.naive_repair_id).length;
  const recommended = plan.repairs.find((repair) => repair.id === plan.recommended_repair_id);
  const stages = [
    { label: "Intention", value: "One stated plan", tone: "text-paper" },
    { label: "Possibilities", value: `${alternatives} tested alternative${alternatives === 1 ? "" : "s"}`, tone: "text-tide" },
    { label: "Stress test", value: `${failures} discovered failure${failures === 1 ? "" : "s"}`, tone: failures ? "text-fault" : "text-moss" },
    { label: "Recommendation", value: recommended?.label ?? "No feasible repair", tone: recommended ? "text-moss" : "text-clay" },
  ];
  return (
    <section className="mb-4 rounded-card border border-white/10 bg-[#10141a] p-4" aria-label="Future story">
      <div className="flex flex-wrap items-center gap-2">
        {stages.map((stage, index) => (
          <div key={stage.label} className="flex min-w-[130px] flex-1 items-center gap-2">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.14em] text-mute">{stage.label}</p>
              <p className={`mt-1 truncate text-sm ${stage.tone}`}>{stage.value}</p>
            </div>
            {index < stages.length - 1 ? <span className="hidden text-mute sm:block" aria-hidden>→</span> : null}
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-mute">
        This story is projected from the evaluated graph, not a decorative prediction. Select a branch to inspect its evidence.
      </p>
    </section>
  );
}
