import { CalendarDays, Mail, Plane, SlidersHorizontal } from "lucide-react";
import type { SampleRecord } from "../api/types";

const ICONS = { Calendar: CalendarDays, Email: Mail, Reservation: Plane, Preference: SlidersHorizontal } as const;

export function SampleWorkspace({
  records,
  open,
  onToggle,
  onLoad,
}: {
  records: SampleRecord[];
  open: boolean;
  onToggle: () => void;
  onLoad: () => void;
}) {
  const groups = [...new Set(records.map((record) => record.source))];
  return (
    <section className="mt-6 rounded-card border border-white/10 bg-white/[0.03] p-4" aria-label="Sample workspace">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-tide">Demo Workspace</p>
          <p className="mt-1 text-sm text-paper">Synthetic context, kept separate from live accounts.</p>
        </div>
        <button type="button" className="rounded-control border border-tide/40 px-3 py-2 text-xs text-tide" onClick={onLoad}>
          Load Sample Workspace
        </button>
      </div>
      <button type="button" className="mt-3 text-xs text-mute" aria-expanded={open} onClick={onToggle}>
        {open ? "Hide sample records" : `Inspect ${records.length} sample records`}
      </button>
      {open ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {groups.map((group) => {
            const Icon = ICONS[group as keyof typeof ICONS] ?? SlidersHorizontal;
            return (
              <div key={group} className="rounded-control border border-white/10 bg-black/10 p-3">
                <p className="flex items-center gap-2 text-xs uppercase tracking-[0.12em] text-mute">
                  <Icon className="h-3.5 w-3.5 text-tide" aria-hidden /> Sample {group}
                </p>
                <ul className="mt-2 space-y-2 text-xs leading-relaxed text-paper">
                  {records.filter((record) => record.source === group).map((record) => <li key={record.record_id}>{record.text}</li>)}
                </ul>
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
