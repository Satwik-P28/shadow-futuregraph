import type { TraceEvent } from "../api/types";

export function DecisionTrace({
  open,
  events,
  onToggle,
}: {
  open: boolean;
  events: TraceEvent[];
  onToggle: () => void;
}) {
  return (
    <section>
      <button type="button" className="text-[11px] uppercase tracking-[0.16em] text-mute" aria-expanded={open} onClick={onToggle}>
        Decision trace
      </button>
      {open ? (
        events.length ? (
          <ol className="mt-3 max-w-md space-y-2">
            {events.map((event) => (
              <li key={event.event_id} className="grid grid-cols-[7.5rem_1fr] gap-3 text-xs">
                <span className="text-mute">{event.timestamp}</span>
                <span className="text-paper">{event.event_type}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-2 text-xs text-mute">No trace events yet.</p>
        )
      ) : null}
    </section>
  );
}
