import type { PlanView } from "../api/types";

export function money(value: number): string {
  const rounded = Math.round(value);
  if (rounded > 0) return `+$${rounded}`;
  if (rounded < 0) return `-$${Math.abs(rounded)}`;
  return "$0";
}

export function actionLabel(plan: PlanView, actionId: string): string {
  const node = plan.graph?.nodes.find((item) => item.id === `act:${actionId}`);
  if (node) return node.label;
  return actionId.replaceAll("_", " ");
}

export function repairActions(plan: PlanView, repairId: string): string[] {
  const targets = new Set(
    (plan.graph?.edges ?? [])
      .filter((edge) => edge.source === `repair:${repairId}` && edge.type === "ENABLES")
      .map((edge) => edge.target),
  );
  return (plan.graph?.nodes ?? []).filter((node) => targets.has(node.id)).map((node) => node.label);
}

export const STAGE_LABELS: Record<string, string> = {
  RETRIEVING_CONTEXT: "Reading personal context",
  BUILDING_GRAPH: "Building future graph",
  SEARCHING_FAILURES: "Searching failure paths",
  TESTING_REPAIRS: "Testing repairs",
  READY: "Ready",
};
