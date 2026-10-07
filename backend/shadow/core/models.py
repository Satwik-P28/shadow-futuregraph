"""Schemas shared by the pipeline, API, and fixtures."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from shadow.core.expr import Expr


class EpistemicStatus(str, Enum):
    VERIFIED = "VERIFIED"
    COMPUTED = "COMPUTED"
    ESTIMATED = "ESTIMATED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class NodeType(str, Enum):
    CURRENT_STATE = "CURRENT_STATE"
    ACTION = "ACTION"
    EXOGENOUS_EVENT = "EXOGENOUS_EVENT"
    DERIVED_STATE = "DERIVED_STATE"
    CONSTRAINT = "CONSTRAINT"
    OUTCOME = "OUTCOME"
    FAILURE = "FAILURE"
    REPAIR = "REPAIR"
    EVIDENCE = "EVIDENCE"
    UNKNOWN = "UNKNOWN"


class EdgeType(str, Enum):
    CAUSES = "CAUSES"
    CONSTRAINS = "CONSTRAINS"
    DEPENDS_ON = "DEPENDS_ON"
    ENABLES = "ENABLES"
    PRECEDES = "PRECEDES"
    VIOLATES = "VIOLATES"
    MITIGATES = "MITIGATES"
    SUPPORTED_BY = "SUPPORTED_BY"
    INVALIDATES = "INVALIDATES"


class WorldFact(BaseModel):
    id: str
    subject: str
    predicate: str
    value: Any
    valid_from: str | None = None
    valid_to: str | None = None
    observed_at: str
    source_type: str
    source_id: str
    epistemic_status: EpistemicStatus
    confidence: float | None = None
    privacy_label: str = "personal"
    supersedes: str | None = None
    tags: list[str] = Field(default_factory=list)
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Variable(BaseModel):
    id: str
    label: str
    role: Literal["controllable", "exogenous", "derived", "fixed"]
    vtype: Literal["number", "bool", "category"]
    baseline: Any = None
    lower: float | None = None
    upper: float | None = None
    scale: float | None = None
    unit: str = ""
    epistemic_status: EpistemicStatus
    distribution: Literal["point", "uniform", "unknown"] = "point"
    formula: Expr | None = None
    show_in_diff: bool = False
    detail: bool = False
    privacy_label: str = "personal"


class Constraint(BaseModel):
    id: str
    label: str
    kind: Literal["temporal", "numeric", "equality", "boolean", "resource", "sequence"]
    hardness: Literal["hard", "soft"]
    expr: Expr
    description: str
    relaxable: bool = False


class ActionDef(BaseModel):
    id: str
    action_type: str
    label: str
    resource: str
    effects: dict[str, Any] = Field(default_factory=dict)
    cost: float = 0
    reversible: bool = True
    compensatable: bool = True
    irreversible: bool = False
    impacts_others: int = 0
    retryable: bool = True


class Bundle(BaseModel):
    id: str
    label: str
    action_ids: list[str]
    rationale: str = ""


class Sensitivity(BaseModel):
    id: str
    variable: str
    if_true_effects: dict[str, Any] = Field(default_factory=dict)
    description: str


class WorldEvent(BaseModel):
    id: str
    label: str
    description: str
    set_baseline: dict[str, Any] = Field(default_factory=dict)
    set_distribution: dict[str, Literal["point", "uniform", "unknown"]] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: str
    title: str
    domain: str
    plan_prompt: str
    variables: list[Variable]
    constraints: list[Constraint]
    actions: list[ActionDef]
    bundles: list[Bundle]
    facts: list[WorldFact]
    events: list[WorldEvent] = Field(default_factory=list)
    sensitivities: list[Sensitivity] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Goal(BaseModel):
    id: str
    description: str


class ConstraintSpec(BaseModel):
    id: str
    description: str
    hardness: Literal["hard", "soft"]
    epistemic_status: EpistemicStatus


class DependencyProposal(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    rationale: str
    epistemic_status: EpistemicStatus = EpistemicStatus.INFERRED


class UncertainVariable(BaseModel):
    id: str
    description: str
    why_material: str


class HazardHypothesis(BaseModel):
    id: str
    description: str
    related_variables: list[str] = Field(default_factory=list)


class PlanSpec(BaseModel):
    goals: list[Goal]
    hard_constraints: list[ConstraintSpec]
    soft_preferences: list[ConstraintSpec] = Field(default_factory=list)
    dependencies: list[DependencyProposal] = Field(default_factory=list)
    uncertain_variables: list[UncertainVariable] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    hazards: list[HazardHypothesis] = Field(default_factory=list)
    intended_bundle_id: str | None = None


class ProposedRepair(BaseModel):
    id: str
    label: str
    action_ids: list[str]
    rationale: str = ""


class RepairProposal(BaseModel):
    repairs: list[ProposedRepair]


class GraphNode(BaseModel):
    id: str
    label: str
    type: NodeType
    epistemic_status: EpistemicStatus
    provenance: str
    confidence: float | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    x: float = 0
    y: float = 0
    hidden_by_default: bool = False


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: EdgeType
    label: str
    epistemic_status: EpistemicStatus
    provenance: str
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FutureGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Perturbation(BaseModel):
    variable: str
    label: str
    baseline: Any
    value: Any
    normalized_magnitude: float
    provenance: str
    controllability: Literal["exogenous", "controllable"]


class MinimalFailureSet(BaseModel):
    id: str
    bundle_id: str
    perturbations: list[Perturbation]
    violated_constraints: list[str]
    severity: Literal["hard", "soft"]
    normalized_distance: float
    causal_trace: list[str]
    repairable: bool
    probability: None = None


class RepairMetrics(BaseModel):
    id: str
    label: str
    action_ids: list[str]
    source: Literal["catalog", "model"]
    hard_violations: int
    unresolved_hard: int
    soft_violations: int
    failure_radius: float | None
    failure_radius_label: str
    modeled_success_rate: float | None
    success_rate_basis: str
    additional_cost: float
    changed_items: int
    reversibility: float
    impact_on_others: int
    unresolved_unknowns: list[str]
    feasible: bool
    status: Literal["feasible", "infeasible", "unresolved"]
    failures: list[MinimalFailureSet] = Field(default_factory=list)
    worlds_simulated: int = 0
    dominated: bool = False
    recommended: bool = False
    rationale: str = ""


class DiffEntry(BaseModel):
    id: str
    label: str
    before: str
    after: str
    changed: bool


class FutureDiff(BaseModel):
    before_label: str
    after_label: str
    entries: list[DiffEntry]
    before_failure: str
    after_failure: str
    unknowns: list[str]


class ContractAction(BaseModel):
    action_id: str
    action_type: str
    resource: str
    max_cost: float


class Assumption(BaseModel):
    id: str
    description: str
    variable: str | None = None
    expected: Any = None
    status: Literal["holding", "invalidated", "updated"] = "holding"


class FutureContract(BaseModel):
    contract_id: str
    plan_id: str
    approved_future_id: str
    created_at: str
    expires_at: str
    goals: list[str]
    invariants: list[str]
    assumptions: list[Assumption]
    allowed_actions: list[ContractAction]
    resource_scopes: list[str]
    spending_limit: float
    forbidden_actions: list[str]
    verification_requirements: list[str]
    compensation_actions: list[str]
    provenance: str
    status: Literal["ACTIVE", "STALE", "REAFFIRMED", "COMPLETED", "HALTED"] = "ACTIVE"


class RuntimeEvent(BaseModel):
    event_id: str
    plan_id: str
    timestamp: str
    event_type: str
    payload: dict[str, Any]
    payload_hash: str
    provenance: str


class CoverageReport(BaseModel):
    resolved: int
    estimated: int
    inferred: int
    unknown: int
    unknown_ids: list[str]
    summary: str
    percentage: None = None
