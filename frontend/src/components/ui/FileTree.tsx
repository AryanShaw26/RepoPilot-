import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronRight, FileCode2, Folder, FolderOpen } from "lucide-react";
import { getTree } from "../../api/repositories";
import type { TreeNode } from "../../types";
import { ErrorState } from "./ErrorState";
import { Skeleton } from "./Skeleton";

interface FileTreeProps {
  repositoryId: string;
  selectedPath?: string;
  onSelect: (node: TreeNode) => void;
}

interface VisibleNode {
  node: TreeNode;
  depth: number;
}

export function FileTree({ repositoryId, selectedPath, onSelect }: FileTreeProps) {
  const [childrenByPath, setChildrenByPath] = useState<Record<string, TreeNode[]>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadedPaths = useRef(new Set<string>());
  const parentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setChildrenByPath({});
    setExpanded(new Set());
    loadedPaths.current = new Set([""]);
    void getTree(repositoryId, "")
      .then((nodes) => {
        if (active) {
          setChildrenByPath({ "": nodes });
          setExpanded(new Set([""]));
        }
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "Unable to load repository tree.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [repositoryId]);

  const toggleDirectory = (path: string) => {
    const shouldExpand = !expanded.has(path);
    setExpanded((current) => {
      const next = new Set(current);
      if (shouldExpand) next.add(path);
      else next.delete(path);
      return next;
    });
    if (shouldExpand && !loadedPaths.current.has(path)) {
      loadedPaths.current.add(path);
      void getTree(repositoryId, path)
        .then((nodes) => setChildrenByPath((current) => ({ ...current, [path]: nodes })))
        .catch((cause: unknown) => {
          loadedPaths.current.delete(path);
          setError(cause instanceof Error ? cause.message : `Unable to expand ${path}.`);
        });
    }
  };

  const visibleNodes = useMemo(() => {
    const result: VisibleNode[] = [];
    const visit = (path: string, depth: number) => {
      for (const node of childrenByPath[path] ?? []) {
        result.push({ node, depth });
        if (node.type === "directory" && expanded.has(node.path)) visit(node.path, depth + 1);
      }
    };
    visit("", 0);
    return result;
  }, [childrenByPath, expanded]);

  const virtualizer = useVirtualizer({
    count: visibleNodes.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 34,
    overscan: 10,
  });

  if (loading) {
    return (
      <div className="space-y-2 p-3" aria-label="Loading repository tree">
        <Skeleton className="h-7 w-3/4" />
        <Skeleton className="h-7 w-1/2" />
        <Skeleton className="h-7 w-2/3" />
      </div>
    );
  }

  if (error && visibleNodes.length === 0) {
    return (
      <ErrorState
        title="File tree unavailable"
        message={error}
        onRetry={() => {
          loadedPaths.current.clear();
          setError(null);
          setLoading(true);
          void getTree(repositoryId, "")
            .then((nodes) => {
              setChildrenByPath({ "": nodes });
              loadedPaths.current.add("");
              setExpanded(new Set([""]));
            })
            .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load repository tree."))
            .finally(() => setLoading(false));
        }}
      />
    );
  }

  return (
    <div>
      {error && <p role="alert" className="px-3 py-2 text-xs text-led-red">{error}</p>}
      <div
        ref={parentRef}
        role="tree"
        aria-label="Repository files"
        className="max-h-[70vh] min-h-48 overflow-auto p-1"
      >
        {visibleNodes.length === 0 ? (
          <p className="p-3 text-sm text-ink-muted">No files in this repository.</p>
        ) : (
          <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const { node, depth } = visibleNodes[virtualRow.index];
              const isDirectory = node.type === "directory";
              const isExpanded = expanded.has(node.path);
              const Icon = isDirectory ? (isExpanded ? FolderOpen : Folder) : FileCode2;
              return (
                <div
                  key={node.path}
                  role="treeitem"
                  aria-expanded={isDirectory ? isExpanded : undefined}
                  aria-selected={selectedPath === node.path}
                  className="absolute left-0 top-0 w-full"
                  style={{
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  <button
                    type="button"
                    onClick={() => (isDirectory ? toggleDirectory(node.path) : onSelect(node))}
                    aria-current={selectedPath === node.path ? "page" : undefined}
                    className={`flex h-full w-full items-center gap-2 rounded px-2 text-left font-mono text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus ${
                      selectedPath === node.path
                        ? "bg-accent/10 text-ink"
                        : "text-ink-muted hover:bg-surface-raised hover:text-ink"
                    }`}
                    style={{ paddingLeft: `${depth * 14 + 8}px` }}
                    title={node.path}
                  >
                    {isDirectory ? (
                      <ChevronRight className={`size-3 shrink-0 transition-transform ${isExpanded ? "rotate-90" : ""}`} aria-hidden="true" />
                    ) : (
                      <span className="w-3 shrink-0" aria-hidden="true" />
                    )}
                    <Icon className={`size-4 shrink-0 ${isDirectory ? "text-accent" : "text-ink-faint"}`} aria-hidden="true" />
                    <span className="truncate">{node.name}</span>
                    <span className="ml-auto shrink-0 font-mono text-[9px] text-led-green">Verified</span>
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
