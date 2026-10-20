const STAGES = ["Intention", "Possibilities", "Stress test", "Recommendation", "Approval"];

export function GuidedDemoControls({
  active,
  stage,
  onStart,
  onPause,
  onSkip,
  onRestart,
}: {
  active: boolean;
  stage: number;
  onStart: () => void;
  onPause: () => void;
  onSkip: () => void;
  onRestart: () => void;
}) {
  return (
    <section className="rounded-card border border-white/10 bg-elevated p-4" aria-label="Guided demo">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-tide">Prepared synthetic scenario</p>
          <p className="mt-1 text-sm text-paper">Watch Shadow work through the NYC future.</p>
        </div>
        {!active ? (
          <button type="button" className="rounded-control bg-tide px-3 py-2 text-xs font-medium text-ink" onClick={onStart}>
            Watch Shadow Work
          </button>
        ) : (
          <div className="flex gap-2">
            <button type="button" className="rounded-control border border-white/10 px-3 py-2 text-xs" onClick={onPause}>Pause</button>
            <button type="button" className="rounded-control border border-white/10 px-3 py-2 text-xs" onClick={onSkip}>Skip</button>
            <button type="button" className="rounded-control border border-white/10 px-3 py-2 text-xs" onClick={onRestart}>Restart</button>
          </div>
        )}
      </div>
      {active ? (
        <ol className="mt-4 flex flex-wrap gap-2">
          {STAGES.map((label, index) => (
            <li key={label} className={`rounded-full border px-2.5 py-1 text-[11px] ${index === stage ? "border-tide text-tide" : index < stage ? "border-moss/50 text-moss" : "border-white/10 text-mute"}`}>
              {index + 1}. {label}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
