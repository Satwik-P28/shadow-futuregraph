import { ArrowRight } from "lucide-react";
import type { ConnectedTools, ModelabilityResult } from "../api/types";
import { AnalysisProgress } from "./AnalysisProgress";
import { ConnectedContext } from "./ConnectedContext";

const TRIP = "Move my NYC trip to Friday and make sure everything still works.";
const MOVE = "I'm thinking about moving apartments next month. Does this plan actually work?";

export const EXAMPLES = { travel: TRIP, apartment: MOVE } as const;

export function HeroPlanInput({
  text,
  exampleId,
  tools,
  busy,
  error,
  modelability,
  onEdit,
  onAnalyze,
  onExample,
}: {
  text: string;
  exampleId: "travel" | "apartment" | null;
  tools: ConnectedTools;
  busy: boolean;
  error: string;
  modelability: ModelabilityResult | null;
  onEdit: (value: string) => void;
  onAnalyze: () => void;
  onExample: (id: "travel" | "apartment") => void;
}) {
  return (
    <div>
      <h1 className="max-w-xl text-4xl font-medium tracking-tight text-paper md:text-5xl md:leading-[1.08]">
        See the future before you commit to it.
      </h1>
      <p className="mt-4 max-w-xl text-base leading-relaxed text-mute md:text-lg">
        Shadow stress-tests your plans, finds hidden failure paths, and repairs them before you act.
      </p>
      <label htmlFor="plan" className="mt-8 block text-[11px] uppercase tracking-[0.16em] text-mute">What are you planning?</label>
      <textarea
        id="plan"
        value={text}
        onChange={(event) => onEdit(event.target.value)}
        placeholder="Tell Shadow what you're planning..."
        className="mt-2 h-28 w-full resize-none rounded-card border border-white/10 bg-elevated px-4 py-3 text-base text-paper placeholder:text-mute/70 sm:h-36"
      />
      <button
        type="button"
        className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-control bg-tide px-4 py-2.5 text-sm font-medium text-ink sm:w-auto"
        onClick={onAnalyze}
        disabled={busy}
      >
        Analyze my future
        <ArrowRight className="h-4 w-4" aria-hidden />
      </button>
      <div className="mt-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-mute">Try an example</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" className="rounded-full border border-white/10 px-3 py-1 text-xs text-paper" onClick={() => onExample("travel")}>
            NYC trip
          </button>
          <button type="button" className="rounded-full border border-white/10 px-3 py-1 text-xs text-paper" onClick={() => onExample("apartment")}>
            Apartment move
          </button>
        </div>
        {exampleId ? <p className="mt-2 text-xs text-mute">Example loaded. This uses a synthetic context, not a live account.</p> : null}
      </div>
      <div className="mt-5">
        <ConnectedContext tools={tools} />
      </div>
      {busy ? <AnalysisProgress active /> : null}
      {error ? <p className="mt-4 text-sm text-fault">{error}</p> : null}
      {modelability?.status === "NEEDS_INFORMATION" ? (
        <div className="mt-4" aria-label="Missing information">
          <p className="text-sm text-clay">I can model this plan, but I need {modelability.missing_information.length} things first:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-paper">
            {modelability.missing_information.map((item) => <li key={item}>{item}</li>)}
          </ul>
          <p className="mt-3 text-[11px] uppercase tracking-[0.16em] text-mute">Missing information</p>
        </div>
      ) : null}
      {modelability?.status === "UNSUPPORTED" ? (
        <div className="mt-4 max-w-xl text-sm text-clay">
          <p>{modelability.reason}</p>
          <p className="mt-2 text-mute">I can still help identify considerations, but I won't pretend to simulate it.</p>
        </div>
      ) : null}
    </div>
  );
}
