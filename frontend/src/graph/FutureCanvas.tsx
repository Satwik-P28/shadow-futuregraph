import { useMemo } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphEdge, GraphNode } from "../api/types";

const KICKER: Record<string, string> = {
  CURRENT_STATE: "Now",
  ACTION: "Action",
  EXOGENOUS_EVENT: "Uncertainty",
  DERIVED_STATE: "State",
  CONSTRAINT: "Constraint",
  OUTCOME: "Outcome",
  FAILURE: "Failure",
  REPAIR: "Repair",
  EVIDENCE: "Evidence",
  UNKNOWN: "Unknown",
};

type NodeData = {
  label: string;
  kind: string;
  dim: boolean;
  hot: boolean;
  approved: boolean;
  delay: number;
};

function ShadowNode({ data }: NodeProps) {
  const payload = data as NodeData;
  return (
    <div
      className={`shadow-node kind-${payload.kind} ${payload.dim ? "is-dim" : ""} ${payload.hot ? "is-hot" : ""} ${payload.approved ? "is-approved" : ""}`}
      style={{ animationDelay: `${payload.delay}ms` }}
    >
      <span className="kicker">{KICKER[payload.kind] ?? payload.kind}</span>
      <span className="label">{payload.label}</span>
    </div>
  );
}

const nodeTypes = { shadow: ShadowNode };

function displayLabel(node: GraphNode, all: GraphNode[]): string {
  if (node.type !== "FAILURE") return node.label;
  const constraint = all.find((item) => item.id === `con:${node.label}`);
  return constraint?.label ?? node.label;
}

function reduceMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

export function FutureCanvas({
  nodes,
  edges,
  expanded,
  highlight,
  repairId,
  approved,
  pulseToken,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  expanded: boolean;
  highlight: string[];
  repairId: string | null;
  approved: boolean;
  pulseToken: number;
  onSelect: (node: GraphNode) => void;
}) {
  const flowNodes = useMemo<Node[]>(() => {
    const story = new Set(["ACTION", "EXOGENOUS_EVENT", "CONSTRAINT", "FAILURE", "REPAIR", "OUTCOME", "UNKNOWN"]);
    const visibleNodes = nodes.filter((node) => expanded || (story.has(node.type) && !node.hidden_by_default));
    const columns = new Map<number, GraphNode[]>();
    for (const node of visibleNodes) columns.set(node.x, [...(columns.get(node.x) ?? []), node]);
    const placed = new Map<string, { x: number; y: number }>();
    [...columns.keys()].sort((a, b) => a - b).forEach((key, column) => {
      columns.get(key)?.forEach((node, index) => placed.set(node.id, { x: column * 270, y: index * 86 }));
    });
    const ordered = [...visibleNodes].sort((a, b) => (placed.get(a.id)?.x ?? 0) - (placed.get(b.id)?.x ?? 0));
    const delay = new Map(ordered.map((node, index) => [node.id, Math.min(index * 16, 320)]));
    const hot = new Set(highlight);
    return visibleNodes.map((node) => {
      const otherRepair = node.type === "REPAIR" && repairId !== null && node.id !== `repair:${repairId}`;
      const otherFailure = node.type === "FAILURE" && repairId !== null && !node.id.startsWith(`failure:${repairId}:`);
      return {
        id: node.id,
        type: "shadow",
        position: placed.get(node.id) ?? { x: node.x, y: node.y },
        data: {
          label: displayLabel(node, nodes),
          kind: node.type,
          dim: (hot.size > 0 && !hot.has(node.id)) || otherRepair || otherFailure,
          hot: hot.has(node.id),
          approved: approved && node.id === `repair:${repairId}`,
          delay: delay.get(node.id) ?? 0,
        },
        style: { width: 188, background: "transparent", border: "none", padding: 0, borderRadius: 12 },
      };
    });
  }, [nodes, expanded, highlight, repairId, approved]);
  const visible = new Set(flowNodes.map((node) => node.id));
  const calm = reduceMotion();
  const flowEdges: Edge[] = edges
    .filter((edge) => visible.has(edge.source) && visible.has(edge.target))
    .map((edge) => {
      const hot = highlight.includes(edge.source) || highlight.includes(edge.target);
      const failure = edge.type === "VIOLATES" || edge.type === "CAUSES";
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: hot && !calm,
        style: { stroke: hot || failure ? "#d37b6e" : "rgba(255,255,255,0.22)", strokeWidth: hot ? 1.6 : 1.15 },
      };
    });
  return (
    <div className="h-[420px] overflow-hidden rounded-card border border-white/10 bg-[#0e1116] lg:h-[min(640px,calc(100vh-13rem))]" aria-label="Future graph">
      <ReactFlow
        key={pulseToken}
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.35}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => {
          const match = nodes.find((item) => item.id === node.id);
          if (match) onSelect(match);
        }}
      >
        <Background color="rgba(255,255,255,0.04)" gap={28} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
