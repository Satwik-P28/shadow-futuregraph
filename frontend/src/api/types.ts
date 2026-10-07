export type GraphNode = {
  id: string;
  label: string;
  type: string;
  epistemic_status: string;
  provenance: string;
  x: number;
  y: number;
  hidden_by_default: boolean;
  metadata: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string;
  epistemic_status: string;
};

export type Failure = {
  id: string;
  violated_constraints: string[];
  normalized_distance: number;
  causal_trace: string[];
  perturbations: { variable: string; label: string; baseline: number; value: number }[];
};

export type Repair = {
  id: string;
  label: string;
  status: string;
  feasible: boolean;
  failure_radius: number | null;
  failure_radius_label: string;
  additional_cost: number;
  changed_items: number;
  hard_violations: number;
  recommended: boolean;
  dominated: boolean;
  failures: Failure[];
};

export type PlanView = {
  id: string;
  text: string;
  scenario_id: string;
  status: string;
  provider_mode: string;
  stages: { name: string }[];
  coverage: { summary: string; unknown: number; percentage: null } | null;
  graph: { nodes: GraphNode[]; edges: GraphEdge[] } | null;
  naive_repair_id: string | null;
  recommended_repair_id: string | null;
  repairs: Repair[];
  failures: Failure[];
  diff: {
    before_label: string;
    after_label: string;
    before_failure: string;
    after_failure: string;
    unknowns: string[];
    entries: { id: string; label: string; before: string; after: string; changed: boolean }[];
  } | null;
  reconciliation: { matched: boolean; message: string } | null;
  observability: { model_calls: number; worlds_simulated: number; repairs_tested: number };
  no_feasible_message: string | null;
  contract: { status: string } | null;
};

export type TraceEvent = { event_id: string; event_type: string; timestamp: string; payload: Record<string, unknown> };
