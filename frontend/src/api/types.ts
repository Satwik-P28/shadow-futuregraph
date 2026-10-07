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

export type ModelabilityStatus = "SUPPORTED" | "NEEDS_INFORMATION" | "UNSUPPORTED" | "CONTRADICTORY";

export type ModelabilityResult = {
  status: ModelabilityStatus;
  reason: string;
  missing_information: string[];
  compiled_constraints: string[];
  compiled_dependencies: string[];
  available_actions: string[];
  selected_skill: string | null;
  provenance: string;
};

export type FreeformResponse = {
  modelability: ModelabilityResult;
  plan: PlanView | null;
};

export type ConnectedTools = {
  calendar: string;
  mail: string;
  travel: string;
  search: string;
};

export type PlanView = {
  id: string;
  text: string;
  scenario_id: string;
  status: string;
  provider_mode: string;
  compiled_from?: string | null;
  understanding?: {
    status: string;
    reason: string;
    missing: string[];
    shown: { source: string; extracted: string; role: string }[];
  } | null;
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
  contract: {
    status: string;
    spending_limit?: number;
    allowed_actions?: { action_id: string; action_type: string; resource: string; max_cost: number }[];
    forbidden_actions?: string[];
  } | null;
  watch?: {
    monitoring: boolean;
    approved_futures: number;
    last_checked_at: string | null;
    drift_status: string | null;
    message: string | null;
    skill_name: string | null;
  };
  memory?: { label: string; source: string } | null;
};

export type TraceEvent = { event_id: string; event_type: string; timestamp: string; payload: Record<string, unknown> };
