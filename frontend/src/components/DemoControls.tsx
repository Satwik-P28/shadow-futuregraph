import { useState } from "react";

const EVENTS = [
  ["delay_74", "+74 min delay"],
  ["fare_increase", "Fare +$80"],
  ["hotel_canceled", "Hotel canceled"],
] as const;

export function DemoControls({ onInject }: { onInject: (eventId: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        className="text-xs uppercase tracking-[0.14em] text-mute"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        Inject world change
      </button>
      {open ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {EVENTS.map(([id, label]) => (
            <button key={id} type="button" className="rounded-full border border-white/10 px-3 py-1 text-xs" onClick={() => onInject(id)}>
              {label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
