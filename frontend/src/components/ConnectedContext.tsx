import { Calendar, Mail, Plane, Search } from "lucide-react";
import type { ConnectedTools } from "../api/types";

const ITEMS = [
  ["calendar", "Calendar", Calendar],
  ["mail", "Mail", Mail],
  ["travel", "Travel", Plane],
  ["search", "Search", Search],
] as const;

export function ConnectedContext({ tools }: { tools: ConnectedTools }) {
  return (
    <div aria-label="Connected context">
      <p className="text-[11px] uppercase tracking-[0.16em] text-mute">Connected context</p>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
        {ITEMS.map(([key, label, Icon]) => {
          const status = tools[key];
          const on = status !== "OFF";
          return (
            <li key={key} className="flex items-center gap-1.5 text-xs text-paper">
              <Icon className="h-3.5 w-3.5 text-mute" aria-hidden />
              <span className={`h-1.5 w-1.5 rounded-full ${on ? "bg-tide" : "border border-mute"}`} aria-hidden />
              <span>{label}: {status}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
