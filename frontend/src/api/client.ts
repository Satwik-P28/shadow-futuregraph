import type { PlanView, TraceEvent } from "./types";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
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

export async function loadBenchmark(): Promise<{ available: boolean; summary: unknown }> {
  return json(await fetch("/api/benchmarks/latest"));
}
