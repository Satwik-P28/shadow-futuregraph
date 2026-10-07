import { useMemo } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphEdge, GraphNode } from "../api/types";

const fill: Record<string, string> = {
  FAILURE: "#3a2422",
  UNKNOWN: "#3a3224",
  OUTCOME: "#243028",
  REPAIR: "#243028",
  CONSTRAINT: "#243038",
  EXOGENOUS_EVENT: "#2a2c28",
};

export function FutureCanvas({
  nodes,
  edges,
  expanded,
  highlight,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  expanded: boolean;
  highlight: string[];
  onSelect: (node: GraphNode) => void;
}) {
  const flowNodes = useMemo<Node[]>(
    () =>
      nodes
        .filter((node) => expanded || !node.hidden_by_default)
        .map((node) => ({
          id: node.id,
          position: { x: node.x, y: node.y },
          data: { label: node.label },
          style: {
            background: fill[node.type] ?? "#1a1d24",
            color: "#ece8e1",
            border: highlight.includes(node.id) ? "1px solid #e07a6a" : "1px solid #31353d",
            borderRadius: 8,
            fontSize: 12,
            width: 180,
            padding: 8,
          },
        })),
    [nodes, expanded, highlight],
  );
  const visible = new Set(flowNodes.map((node) => node.id));
  const flowEdges: Edge[] = edges
    .filter((edge) => visible.has(edge.source) && visible.has(edge.target))
    .map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.type,
      style: { stroke: highlight.includes(edge.source) || highlight.includes(edge.target) ? "#e07a6a" : "#5c616b" },
    }));
  return (
    <div className="h-[50vh] min-h-[360px] overflow-hidden rounded-lg border border-line bg-ink lg:h-[640px]" aria-label="Future graph">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        fitView
        minZoom={0.4}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => {
          const match = nodes.find((item) => item.id === node.id);
          if (match) onSelect(match);
        }}
      >
        <Background color="#31353d" gap={24} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
