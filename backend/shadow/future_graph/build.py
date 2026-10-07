"""Build a bounded DAG of material futures from a scenario and search results."""

from __future__ import annotations

import networkx as nx

from shadow.core.expr import references
from shadow.core.models import (
    EdgeType,
    EpistemicStatus,
    FutureGraph,
    GraphEdge,
    GraphNode,
    NodeType,
    RepairMetrics,
    Scenario,
)
from shadow.simulation.engine import upstream_vars

NODE_CAP = 80
EDGE_CAP = 160


def build_graph(
    scenario: Scenario,
    repairs: list[RepairMetrics],
    *,
    naive_id: str | None,
    recommended_id: str | None,
) -> FutureGraph:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def add_node(node: GraphNode) -> None:
        nodes.setdefault(node.id, node)

    def add_edge(edge: GraphEdge) -> None:
        if any(item.id == edge.id for item in edges):
            return
        edges.append(edge)

    for fact in scenario.facts:
        node_type = NodeType.UNKNOWN if fact.epistemic_status == EpistemicStatus.UNKNOWN else NodeType.EVIDENCE
        if fact.epistemic_status == EpistemicStatus.VERIFIED and fact.predicate in {"scheduled", "current_booking", "status"}:
            node_type = NodeType.CURRENT_STATE
        add_node(
            GraphNode(
                id=f"fact:{fact.id}",
                label=fact.text[:88],
                type=node_type,
                epistemic_status=fact.epistemic_status,
                provenance=f"{fact.source_type}:{fact.source_id}",
                confidence=fact.confidence,
                valid_from=fact.valid_from,
                valid_to=fact.valid_to,
                metadata={"fact_id": fact.id, "predicate": fact.predicate, "value": fact.value},
                hidden_by_default=False,
            )
        )

    for var in scenario.variables:
        if var.epistemic_status == EpistemicStatus.UNKNOWN or var.distribution == "unknown":
            kind = NodeType.UNKNOWN
        elif var.role == "exogenous":
            kind = NodeType.EXOGENOUS_EVENT
        elif var.role == "derived":
            kind = NodeType.DERIVED_STATE
        else:
            kind = NodeType.CURRENT_STATE
        add_node(
            GraphNode(
                id=f"var:{var.id}",
                label=var.label,
                type=kind,
                epistemic_status=var.epistemic_status,
                provenance="scenario",
                metadata={"role": var.role, "unit": var.unit, "baseline": var.baseline},
                hidden_by_default=var.detail,
            )
        )
        if var.formula is not None:
            for ref in references(var.formula):
                add_edge(
                    GraphEdge(
                        id=f"causes:{ref}:{var.id}",
                        source=f"var:{ref}",
                        target=f"var:{var.id}",
                        type=EdgeType.CAUSES,
                        label="causes",
                        epistemic_status=EpistemicStatus.COMPUTED,
                        provenance="formula",
                    )
                )

    for constraint in scenario.constraints:
        add_node(
            GraphNode(
                id=f"con:{constraint.id}",
                label=constraint.label,
                type=NodeType.CONSTRAINT,
                epistemic_status=EpistemicStatus.VERIFIED,
                provenance="scenario",
                metadata={"hardness": constraint.hardness, "kind": constraint.kind},
            )
        )
        for ref in references(constraint.expr):
            add_edge(
                GraphEdge(
                    id=f"dep:{constraint.id}:{ref}",
                    source=f"var:{ref}",
                    target=f"con:{constraint.id}",
                    type=EdgeType.CONSTRAINS,
                    label="constrains",
                    epistemic_status=EpistemicStatus.COMPUTED,
                    provenance="constraint",
                )
            )

    interesting = set()
    for repair in repairs:
        if repair.recommended or repair.id == naive_id or repair.status != "feasible":
            interesting.add(repair.id)
    for repair in repairs:
        if repair.id not in interesting and repair.dominated:
            continue
        if repair.id not in interesting and not repair.recommended and repair.id != naive_id:
            if repair.status == "feasible" and repair.id != recommended_id:
                continue
        add_node(
            GraphNode(
                id=f"repair:{repair.id}",
                label=repair.label,
                type=NodeType.REPAIR,
                epistemic_status=EpistemicStatus.COMPUTED,
                provenance=repair.source,
                metadata={"status": repair.status, "recommended": repair.recommended},
            )
        )
        for action_id in repair.action_ids:
            action = next(item for item in scenario.actions if item.id == action_id)
            add_node(
                GraphNode(
                    id=f"act:{action.id}",
                    label=action.label,
                    type=NodeType.ACTION,
                    epistemic_status=EpistemicStatus.VERIFIED,
                    provenance="catalog",
                    metadata={"resource": action.resource, "action_type": action.action_type},
                )
            )
            add_edge(
                GraphEdge(
                    id=f"en:{repair.id}:{action.id}",
                    source=f"repair:{repair.id}",
                    target=f"act:{action.id}",
                    type=EdgeType.ENABLES,
                    label="enables",
                    epistemic_status=EpistemicStatus.COMPUTED,
                    provenance="bundle",
                )
            )
            for target, _value in action.effects.items():
                add_edge(
                    GraphEdge(
                        id=f"set:{action.id}:{target}",
                        source=f"act:{action.id}",
                        target=f"var:{target}",
                        type=EdgeType.ENABLES,
                        label="sets",
                        epistemic_status=EpistemicStatus.COMPUTED,
                        provenance="effect",
                    )
                )

    for repair in repairs:
        for failure in repair.failures:
            add_node(
                GraphNode(
                    id=f"failure:{repair.id}:{failure.id}",
                    label=failure.violated_constraints[0],
                    type=NodeType.FAILURE,
                    epistemic_status=EpistemicStatus.COMPUTED,
                    provenance="failure-search",
                    metadata={
                        "distance": failure.normalized_distance,
                        "constraints": failure.violated_constraints,
                        "variables": [item.variable for item in failure.perturbations],
                    },
                )
            )
            for constraint_id in failure.violated_constraints:
                add_edge(
                    GraphEdge(
                        id=f"violates:{repair.id}:{failure.id}:{constraint_id}",
                        source=f"failure:{repair.id}:{failure.id}",
                        target=f"con:{constraint_id}",
                        type=EdgeType.VIOLATES,
                        label="violates",
                        epistemic_status=EpistemicStatus.COMPUTED,
                        provenance="failure-search",
                    )
                )
            for item in failure.perturbations:
                add_edge(
                    GraphEdge(
                        id=f"pert:{repair.id}:{failure.id}:{item.variable}",
                        source=f"var:{item.variable}",
                        target=f"failure:{repair.id}:{failure.id}",
                        type=EdgeType.CAUSES,
                        label="perturbs",
                        epistemic_status=EpistemicStatus.ESTIMATED,
                        provenance="failure-search",
                    )
                )

    add_node(
        GraphNode(
            id="outcome:plan",
            label="Approved outcome" if recommended_id else "No feasible outcome yet",
            type=NodeType.OUTCOME,
            epistemic_status=EpistemicStatus.COMPUTED,
            provenance="repair-evaluator",
        )
    )
    if recommended_id:
        add_edge(
            GraphEdge(
                id=f"mitigates:{recommended_id}",
                source=f"repair:{recommended_id}",
                target="outcome:plan",
                type=EdgeType.MITIGATES,
                label="mitigates",
                epistemic_status=EpistemicStatus.COMPUTED,
                provenance="repair-evaluator",
            )
        )

    _attach_facts(scenario, add_edge)
    pruned = _prune(nodes, edges)
    _layout(pruned)
    return pruned


def _attach_facts(scenario: Scenario, add_edge) -> None:
    for fact in scenario.facts:
        for constraint in scenario.constraints:
            text = f"{fact.text} {fact.subject}".lower()
            if any(token in text for token in constraint.label.lower().split() if len(token) > 4):
                add_edge(
                    GraphEdge(
                        id=f"sup:{fact.id}:{constraint.id}",
                        source=f"fact:{fact.id}",
                        target=f"con:{constraint.id}",
                        type=EdgeType.SUPPORTED_BY,
                        label="supported by",
                        epistemic_status=fact.epistemic_status,
                        provenance=fact.source_id,
                    )
                )
                break


def _prune(nodes: dict[str, GraphNode], edges: list[GraphEdge]) -> FutureGraph:
    graph = nx.DiGraph()
    for node in nodes.values():
        graph.add_node(node.id)
    for edge in edges:
        if edge.source in nodes and edge.target in nodes:
            graph.add_edge(edge.source, edge.target)
    if not nx.is_directed_acyclic_graph(graph):
        # Drop back-edges introduced by evidence links. Constraints stay acyclic upstream.
        cycle_edges = list(nx.find_cycle(graph))
        for source, target in cycle_edges:
            graph.remove_edge(source, target)
    keep: set[str] = set()
    anchors = [node_id for node_id in graph if node_id.startswith("con:") or node_id.startswith("outcome:")]
    for anchor in anchors:
        keep.add(anchor)
        keep |= nx.ancestors(graph, anchor)
    for node_id in list(keep):
        for _src, dst in graph.out_edges(node_id):
            if dst.startswith("failure:") or dst.startswith("outcome:"):
                keep.add(dst)
    # Failures point at constraints, so they are ancestors. Actions and repairs too.
    if len(keep) > NODE_CAP:
        detail = {node_id for node_id in keep if nodes[node_id].hidden_by_default}
        overflow = len(keep) - NODE_CAP
        for node_id in list(detail)[:overflow]:
            keep.discard(node_id)
    kept_nodes = [nodes[node_id] for node_id in nodes if node_id in keep]
    kept_edges = [edge for edge in edges if edge.source in keep and edge.target in keep][:EDGE_CAP]
    return FutureGraph(nodes=kept_nodes, edges=kept_edges)


def _layout(graph: FutureGraph) -> None:
    order = {
        NodeType.CURRENT_STATE: 0,
        NodeType.EVIDENCE: 0,
        NodeType.UNKNOWN: 1,
        NodeType.EXOGENOUS_EVENT: 1,
        NodeType.ACTION: 2,
        NodeType.REPAIR: 2,
        NodeType.DERIVED_STATE: 3,
        NodeType.CONSTRAINT: 4,
        NodeType.FAILURE: 5,
        NodeType.OUTCOME: 6,
    }
    columns: dict[int, list[GraphNode]] = {}
    for node in graph.nodes:
        columns.setdefault(order.get(node.type, 3), []).append(node)
    for column, members in columns.items():
        for index, node in enumerate(members):
            node.x = float(column * 240)
            node.y = float(index * 78)


def trace_node_ids(scenario: Scenario, constraint_id: str) -> list[str]:
    constraint = next(item for item in scenario.constraints if item.id == constraint_id)
    return [f"var:{item}" for item in upstream_vars(scenario, constraint)] + [f"con:{constraint_id}"]
