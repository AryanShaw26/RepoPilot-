import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dagre from "dagre";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getDependencyGraph } from "../api/graph";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Panel } from "../components/ui/Panel";
import { Segmented } from "../components/ui/Segmented";
import { Statement } from "../components/ui/Statement";
import type { GraphNode } from "../types";
import { LoadingState, PageHeading, QueryError, TrustNote } from "./shared";

type GraphLevel = "file" | "folder";
type GraphNodeData = {
  label: React.ReactNode;
  path: string;
  node: GraphNode;
};

function layoutGraph(
  graphNodes: GraphNode[],
  graphEdges: Array<{ id: string; source: string; target: string; kind: string; weight: number }>
): { nodes: Node<GraphNodeData>[]; edges: Edge[] } {
  const layout = new dagre.graphlib.Graph();
  layout.setDefaultEdgeLabel(() => ({}));
  layout.setGraph({ rankdir: "LR", nodesep: 36, ranksep: 76, marginx: 24, marginy: 24 });
  const nodeIds = new Set(graphNodes.map((node) => node.id));
  const width = 228;
  const height = 88;
  graphNodes.forEach((node) => layout.setNode(node.id, { width, height }));
  graphEdges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .forEach((edge) => layout.setEdge(edge.source, edge.target));
  dagre.layout(layout);

  const nodes: Node<GraphNodeData>[] = graphNodes.map((node) => {
    const position = layout.node(node.id);
    return {
      id: node.id,
      type: "default",
      position: { x: position.x - width / 2, y: position.y - height / 2 },
      data: {
        path: node.path,
        node,
        label: (
          <div className="min-w-0">
            <p className="truncate font-mono text-xs font-semibold">{node.label}</p>
            <p className="mt-1 truncate font-mono text-[10px] text-ink-muted">{node.path}</p>
            <p className="mt-1 font-mono text-[9px] text-led-green">Verified · {node.in_degree} in / {node.out_degree} out</p>
          </div>
        ),
      },
      style: {
        width,
        minHeight: height,
        border: `1px solid ${node.in_cycle ? "var(--led-red)" : "var(--edge)"}`,
        borderRadius: "var(--r-sm)",
        padding: 10,
        background: "var(--surface-raised)",
        color: "var(--ink)",
        boxShadow: "var(--elev-1)",
      },
    };
  });
  const edges: Edge[] = graphEdges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      label: `${edge.kind}${edge.weight > 1 ? ` ×${edge.weight}` : ""}`,
      labelStyle: { fill: "var(--ink-muted)", fontSize: 10 },
      labelBgStyle: { fill: "var(--surface-raised)" },
      style: { stroke: "var(--brand)", strokeWidth: 1.5 },
    }));
  return { nodes, edges };
}

export function GraphPage() {
  const { repositoryId = "" } = useParams();
  const navigate = useNavigate();
  const [level, setLevel] = useState<GraphLevel>("file");
  const [includeExternal, setIncludeExternal] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const graph = useQuery({
    queryKey: ["graph", repositoryId, level, includeExternal],
    queryFn: () => getDependencyGraph(repositoryId, level, undefined, includeExternal),
    enabled: Boolean(repositoryId),
  });

  const layout = useMemo(
    () => graph.data ? layoutGraph(graph.data.nodes, graph.data.edges) : { nodes: [], edges: [] },
    [graph.data]
  );
  const handleNodeClick: NodeMouseHandler = (_event, node) => {
    const data = node.data as GraphNodeData;
    setSelectedNode(data.node);
    if (level === "file" && data.node.type === "file") {
      navigate(`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(data.node.path)}`);
    }
  };
  const openSource = () => {
    if (selectedNode?.path) {
      navigate(`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(selectedNode.path)}`);
    }
  };

  return (
    <div>
      <PageHeading
        eyebrow="Dependency map"
        title="Dependencies"
        description="Explore file- and folder-level import relationships and detected cycles."
        actions={<Link to={`/repositories/${repositoryId}/explorer`}><Button variant="ghost">Open explorer</Button></Link>}
      />

      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">Graph resolution</p>
          <Segmented
            label="Graph resolution"
            value={level}
            onChange={setLevel}
            options={[
              { value: "file", label: "Files" },
              { value: "folder", label: "Collapse to folders" },
            ]}
          />
          <p className="mt-2 text-xs text-ink-muted">Folder level aggregates file nodes by directory.</p>
        </div>
        <label className="flex min-h-11 items-center gap-2 font-mono text-xs text-ink-muted">
          <input type="checkbox" checked={includeExternal} onChange={(event) => setIncludeExternal(event.target.checked)} className="size-4 accent-accent" />
          Include external dependencies
        </label>
      </div>

      {graph.isPending ? (
        <LoadingState label="Building dependency graph…" />
      ) : graph.isError ? (
        <QueryError error={graph.error} onRetry={() => void graph.refetch()} />
      ) : graph.data.nodes.length === 0 ? (
        <Panel><EmptyState title="No dependency edges" description="No internal import relationships were found for this repository." /></Panel>
      ) : (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <GraphStat label="Nodes" value={graph.data.stats.total_nodes} />
            <GraphStat label="Edges" value={graph.data.stats.total_edges} />
            <GraphStat label="Cycles detected" value={graph.data.stats.cycles_detected} />
          </div>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
            <Panel className="min-w-0">
              <div className="h-[65vh] min-h-[420px] overflow-hidden rounded-md border border-edge">
                <ReactFlow
                  nodes={layout.nodes}
                  edges={layout.edges}
                  fitView
                  minZoom={0.1}
                  maxZoom={2}
                  onNodeClick={handleNodeClick}
                  aria-label="Repository dependency graph"
                >
                  <Background color="var(--edge)" gap={20} />
                  <Controls />
                  <MiniMap
                    nodeColor={(node) => {
                      const data = node.data as GraphNodeData;
                      return data.node.in_cycle ? "var(--led-red)" : "var(--brand)";
                    }}
                    maskColor="color-mix(in srgb, var(--surface) 70%, transparent)"
                  />
                </ReactFlow>
              </div>
            </Panel>
            <Panel header={<h2 className="font-display text-xl">Selected node</h2>}>
              {selectedNode ? (
                <div className="space-y-3">
                  <Statement text={selectedNode.path} kind="fact" className="break-all font-mono text-xs" />
                  <p className="text-xs text-ink-muted">{selectedNode.type} · {selectedNode.language ?? "language unknown"} · Verified</p>
                  <p className="text-xs text-ink-muted">Inbound: {selectedNode.in_degree} · Outbound: {selectedNode.out_degree} · Verified</p>
                  {selectedNode.in_cycle && <Badge tone="red">Cycle member · Verified</Badge>}
                  <Button size="small" onClick={openSource}>Open in explorer</Button>
                </div>
              ) : (
                <p className="text-sm text-ink-muted">Select a graph node to inspect its metadata.</p>
              )}
            </Panel>
          </div>

          {graph.data.cycles.length > 0 && (
            <Panel className="mt-5" header={<h2 className="font-display text-xl">Detected cycles</h2>}>
              <ul className="space-y-2">
                {graph.data.cycles.map((cycle, index) => (
                  <li key={`${cycle.join("|")}-${index}`} className="rounded border border-led-red/40 bg-surface-inset p-3">
                    <Statement text={cycle.join(" → ")} kind="fact" className="break-all font-mono text-xs" />
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          {graph.data.stats.note && <TrustNote>{graph.data.stats.note}</TrustNote>}
          <TrustNote>Static-analysis map · Verified. Edges are derived from indexed imports; external dependencies appear only when enabled.</TrustNote>
        </>
      )}
    </div>
  );
}

function GraphStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-edge bg-surface-inset p-3 shadow-inset">
      <p className="font-mono text-[10px] uppercase text-ink-muted">{label}</p>
      <p className="font-display text-2xl tabular-nums">{value}</p>
      <p className="font-mono text-[10px] text-led-green">Verified</p>
    </div>
  );
}
