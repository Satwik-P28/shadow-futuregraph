import type { ConnectedTools, FreeformResponse, PlanView, TraceEvent } from "./types";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const raw = await response.text();
    let detail = raw;
    try {
      const body = JSON.parse(raw) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail) detail = body.detail;
    } catch {
      detail = raw;
    }
    throw new Error(detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function analyzeFreeform(
  text: string,
  demoContextId: "travel" | "apartment" | null,
): Promise<FreeformResponse> {
  return json(await fetch("/api/plans/freeform", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, demo_context_id: demoContextId, seed: 7 }),
  }));
}

export type LabVariable = { id: string; label: string; lower: number; upper: number; baseline: number; unit: string };
export type LabResult = {
  overrides: Record<string, number>;
  holds: boolean;
  violated_labels: string[];
  highlight: string[];
  message: string;
  simulation: boolean;
};
export type FutureCard = {
  future_id: string;
  plan_id: string;
  name: string;
  status: string;
  material_unknowns: number;
  nearest_failure: string;
};
export type CrossPlanConflict = {
  conflict_id?: string;
  future_ids: string[];
  future_names?: string[];
  conflict_type?: string;
  resource_id?: string;
  resource_type?: string;
  description?: string;
  violated_constraint?: string;
  causal_path?: string[];
  shared_resource?: string;
  constraint?: string;
  severity: string;
  epistemic_status?: string;
  repairable: boolean;
  provenance?: string;
};

export async function loadFutures(): Promise<{ futures: FutureCard[]; conflicts: CrossPlanConflict[] }> {
  return json(await fetch("/api/futures"));
}

export async function loadLab(id: string): Promise<{ variables: LabVariable[]; simulation: boolean }> {
  return json(await fetch(`/api/plans/${id}/lab`));
}

export async function simulateLab(id: string, overrides: Record<string, number>, repairId: string | null): Promise<LabResult> {
  return json(await fetch(`/api/plans/${id}/lab`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ overrides, repair_id: repairId }),
  }));
}

export async function nearestLab(id: string, repairId: string | null): Promise<LabResult> {
  return json(await fetch(`/api/plans/${id}/lab/nearest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repair_id: repairId }),
  }));
}

export async function loadReceipt(id: string): Promise<{
  approved: string | null;
  executed: string[];
  blocked: string[];
  verification: string | null;
  matched: boolean | null;
  contract_status: string | null;
}> {
  return json(await fetch(`/api/plans/${id}/receipt`));
}

export async function loadPersonalStatus(): Promise<{ connected_tools: ConnectedTools }> {
  return json(await fetch("/api/personal-ai/status"));
}

export async function createPlan(text: string, scenarioId: string): Promise<{ id: string }> {
  return json(await fetch("/api/plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, scenario_id: scenarioId, seed: 7 }),
  }));
}

export async function loadPlan(id: string): Promise<PlanView> {
  return json(await fetch(`/api/plans/${id}`));
}

export async function analyzePlan(id: string): Promise<PlanView> {
  return json(await fetch(`/api/plans/${id}/analyze`, { method: "POST" }));
}

export async function approveRepair(id: string, repairId: string): Promise<void> {
  await json(await fetch(`/api/plans/${id}/repairs/${repairId}/approve`, { method: "POST" }));
}

export async function executePlan(id: string): Promise<{ status: string }> {
  return json(await fetch(`/api/plans/${id}/execute`, { method: "POST" }));
}

export async function injectEvent(id: string, eventId: string): Promise<{
  message: string;
  authority: string;
  approved_future_holds: boolean;
  watch_message?: string;
  drift_status?: string;
  skill_name?: string;
}> {
  return json(await fetch(`/api/plans/${id}/inject-event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_id: eventId }),
  }));
}

export async function attemptAction(id: string, actionId: string): Promise<{ authorized: boolean; message: string }> {
  return json(await fetch(`/api/plans/${id}/actions/attempt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_id: actionId }),
  }));
}

export async function loadEvents(id: string): Promise<TraceEvent[]> {
  const body = await json<{ events: TraceEvent[] }>(await fetch(`/api/plans/${id}/events`));
  return body.events;
}

export async function resetDemo(): Promise<PlanView> {
  return json(await fetch("/api/demo/reset", { method: "POST" }));
}

export async function loadBenchmark(): Promise<{ available: boolean; summary: unknown }> {
  return json(await fetch("/api/benchmarks/latest"));
}
