import { STAGE_LABELS } from "./format";

const ORDER = ["RETRIEVING_CONTEXT", "BUILDING_GRAPH", "SEARCHING_FAILURES", "TESTING_REPAIRS"] as const;

export function AnalysisProgress({ active }: { active: boolean }) {
  return (
    <div role="status" aria-label="Analyzing plan" className="mt-4">
      <p className="text-sm text-paper">Analyzing plan</p>
      <ol className="mt-3 space-y-2">
        {ORDER.map((id, index) => {
          const current = active && index === 0;
          return (
            <li key={id} className="flex items-center gap-2 text-sm">
              <span className={`h-1.5 w-1.5 rounded-full ${current ? "bg-tide" : "border border-mute"}`} aria-hidden />
              <span className={current ? "text-paper" : "text-mute"}>{STAGE_LABELS[id]}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function GraphSkeleton() {
  return (
    <div className="grid h-[420px] grid-cols-2 content-start gap-3 rounded-card border border-white/10 bg-elevated/80 p-5 lg:h-[560px]" aria-hidden>
      {["w-2/3", "w-1/2", "w-3/5", "w-2/5", "w-4/5", "w-3/4"].map((width, index) => (
        <div key={width} className={`h-14 ${width} rounded-control bg-white/5`} style={{ opacity: 1 - index * 0.08 }} />
      ))}
    </div>
  );
}
