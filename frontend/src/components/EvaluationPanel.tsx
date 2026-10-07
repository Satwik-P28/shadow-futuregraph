type Score = { count: number; n: number };

export function EvaluationPanel({
  open,
  summary,
  onToggle,
}: {
  open: boolean;
  summary: string;
  onToggle: () => void;
}) {
  let rows: { name: string; count: number; n: number }[] = [];
  if (summary && !summary.startsWith("No local")) {
    rows = summary.split(" · ").flatMap((part) => {
      const match = part.match(/^(.*): completion (\d+)\/(\d+)/);
      if (!match) return [];
      return [{ name: match[1], count: Number(match[2]), n: Number(match[3]) }];
    });
  }
  return (
    <section aria-label="ShadowBench">
      <button type="button" className="text-[11px] uppercase tracking-[0.16em] text-mute" aria-expanded={open} onClick={onToggle}>
        Evaluation
      </button>
      {open ? (
        <div className="mt-3 max-w-md">
          <p className="text-sm text-paper">30-world live Nemotron pilot</p>
          <p className="text-xs text-mute">Synthetic pilot</p>
          {summary.startsWith("No local") ? <p className="mt-2 text-xs text-mute">{summary}</p> : null}
          <ul className="mt-3 space-y-2">
            {rows.map((row) => (
              <li key={row.name}>
                <div className="flex justify-between text-xs text-mute">
                  <span>{row.name}</span>
                  <span>{row.count}/{row.n}</span>
                </div>
                <div className="mt-1 h-1 rounded-full bg-white/10">
                  <div className="h-1 rounded-full bg-tide" style={{ width: `${row.n ? (row.count / row.n) * 100 : 0}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export function formatBenchmark(summary: { systems: Record<string, { TaskCompletionRate: Score }> }): string {
  const names: Record<string, string> = {
    shadow: "Shadow",
    planner_critic: "Planner + critic",
    planner: "Planner",
    direct: "Direct",
    shadow_no_search: "Shadow without failure search",
  };
  const order = ["shadow", "planner_critic", "planner", "direct", "shadow_no_search"];
  const systems = summary.systems;
  const keys = [...order.filter((key) => key in systems), ...Object.keys(systems).filter((key) => !order.includes(key))];
  return keys
    .map((key) => {
      const row = systems[key].TaskCompletionRate;
      return `${names[key] ?? key}: completion ${row.count}/${row.n}`;
    })
    .join(" · ");
}
