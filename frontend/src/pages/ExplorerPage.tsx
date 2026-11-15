import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams, useParams } from "react-router-dom";
import { explainSymbol, getFileContent, getFileSymbols, getTestsForFile } from "../api/repositories";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { CodeWindow } from "../components/ui/CodeWindow";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { FileTree } from "../components/ui/FileTree";
import { Panel } from "../components/ui/Panel";
import { Statement } from "../components/ui/Statement";
import { useTheme } from "../context/ThemeContext";
import type { TreeNode } from "../types";
import { presentApiError } from "../utils/apiErrors";
import { LoadingState, PageHeading, QueryError } from "./shared";

export function ExplorerPage() {
  const { repositoryId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedSymbolId, setSelectedSymbolId] = useState<string | null>(null);
  const selectedPath = searchParams.get("path") ?? "";
  const lineParam = searchParams.get("line");
  const highlightRange = parseLineRange(lineParam);
  const { theme } = useTheme();
  const file = useQuery({
    queryKey: ["file", repositoryId, selectedPath],
    queryFn: () => getFileContent(repositoryId, selectedPath),
    enabled: Boolean(repositoryId && selectedPath),
  });
  const symbols = useQuery({
    queryKey: ["symbols", repositoryId, selectedPath],
    queryFn: () => getFileSymbols(repositoryId, selectedPath),
    enabled: Boolean(repositoryId && selectedPath),
  });
  const tests = useQuery({
    queryKey: ["tests-for-file", repositoryId, selectedPath],
    queryFn: () => getTestsForFile(repositoryId, selectedPath),
    enabled: Boolean(repositoryId && selectedPath && !file.data?.is_test),
  });
  const explanation = useMutation({
    mutationFn: (symbolId: string) => explainSymbol(repositoryId, symbolId),
  });

  const selectNode = (node: TreeNode) => {
    setSelectedSymbolId(null);
    setSearchParams({ path: node.path });
  };

  return (
    <div>
      <PageHeading
        eyebrow="Repository explorer"
        title="Explore source"
        description="Browse the indexed file tree, inspect source, symbols, and mapped tests."
      />

      <div className="grid min-h-[65vh] gap-4 xl:grid-cols-[minmax(16rem,0.28fr)_minmax(0,0.72fr)]">
        <Panel variant="sunken" className="min-w-0" header={<h2 className="font-display text-lg">File tree</h2>}>
          <FileTree repositoryId={repositoryId} selectedPath={selectedPath} onSelect={selectNode} />
        </Panel>

        <div className="min-w-0 space-y-4">
          {!selectedPath ? (
            <Panel><EmptyState title="Select a file" description="Choose a file in the tree to inspect its source and symbols." /></Panel>
          ) : file.isPending ? (
            <LoadingState label={`Loading ${selectedPath}…`} />
          ) : file.isError ? (
            <QueryError error={file.error} onRetry={() => void file.refetch()} />
          ) : (
            <>
              <Panel>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Statement text={file.data.path} kind="fact" className="break-all font-mono text-sm" />
                    <p className="mt-1 font-mono text-xs text-ink-muted">
                      {file.data.language || "Unknown language"} · {file.data.line_count ?? "—"} lines · {file.data.size_bytes.toLocaleString()} bytes · Verified
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {file.data.is_test && <Badge tone="blue">Test file · Verified</Badge>}
                    {file.data.is_entry_point && <Badge tone="amber">Entry point · Verified</Badge>}
                  </div>
                </div>
              </Panel>

              {file.data.content !== null && file.data.content !== undefined ? (
                <>
                  {lineParam && !highlightRange && (
                    <ErrorState title="Invalid line range" message="Use a positive line number or a start-end range, for example ?line=12-20." />
                  )}
                  <CodeWindow code={file.data.content} path={file.data.path} theme={theme} highlightRange={highlightRange} />
                </>
              ) : (
                <Panel><EmptyState title="Source content unavailable" description="The file metadata is indexed, but source content was not returned." /></Panel>
              )}

              <Panel header={<div className="flex items-center justify-between gap-3"><h2 className="font-display text-xl">Symbols</h2><Badge tone="neutral">{symbols.data?.length ?? 0} · Verified</Badge></div>}>
                {symbols.isPending ? (
                  <p role="status" className="text-sm text-ink-muted">Loading symbols…</p>
                ) : symbols.isError ? (
                  <QueryError error={symbols.error} onRetry={() => void symbols.refetch()} />
                ) : symbols.data.length ? (
                  <ul className="space-y-3">
                    {symbols.data.map((symbol) => (
                      <li key={symbol.id} className="rounded border border-edge bg-surface-inset p-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <Statement text={symbol.qualified_name || symbol.name} kind="fact" className="font-mono text-sm" />
                            <p className="mt-1 font-mono text-xs text-ink-muted">
                              {symbol.kind} · lines {symbol.start_line}–{symbol.end_line} · Verified
                            </p>
                            {symbol.signature && <code className="mt-2 block break-all text-xs text-ink-muted"><Statement text={symbol.signature} kind="fact" /></code>}
                            <Link
                              to={`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(selectedPath)}&line=${symbol.start_line}-${symbol.end_line}`}
                              className="mt-2 inline-block font-mono text-[10px] text-accent underline"
                            >
                              Open lines {symbol.start_line}–{symbol.end_line} · Verified
                            </Link>
                          </div>
                          <Button
                            size="small"
                            onClick={() => {
                              setSelectedSymbolId(symbol.id);
                              explanation.mutate(symbol.id);
                            }}
                          >
                            Explain
                          </Button>
                        </div>
                        {selectedSymbolId === symbol.id && explanation.isError && (
                          <p role="alert" className="mt-2 text-xs text-led-red">{presentApiError(explanation.error).message}</p>
                        )}
                        {selectedSymbolId === symbol.id && explanation.data && (
                          <div className="mt-3 border-t border-edge pt-3">
                            <Statement text={explanation.data.explanation} kind="hypothesis" />
                            {explanation.data.confidence && (
                              <p className="mt-2 font-mono text-[10px] text-ink-muted">Confidence: {explanation.data.confidence}</p>
                            )}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState title="No symbols found" description="No symbols were extracted from this file." />
                )}
              </Panel>

              {!file.data.is_test && (
                <Panel header={<h2 className="font-display text-xl">Mapped tests</h2>}>
                  {tests.isPending ? (
                    <p role="status" className="text-sm text-ink-muted">Checking for mapped tests…</p>
                  ) : tests.isError ? (
                    <QueryError error={tests.error} onRetry={() => void tests.refetch()} />
                  ) : tests.data.length ? (
                    <ul className="space-y-2">
                      {tests.data.map((test, index) => (
                        <li key={`${test.path}-${index}`} className="border-b border-edge pb-2 last:border-0">
                          <Statement text={test.path} kind="fact" className="break-all font-mono text-xs" />
                          <p className="mt-1 text-xs text-ink-muted">{test.method} · Confidence: {test.confidence} · Verified</p>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-ink-muted">No mapped tests were returned for this source file.</p>
                  )}
                </Panel>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function parseLineRange(value: string | null): [number, number] | undefined {
  if (!value) return undefined;
  const match = /^(\d+)(?:-(\d+))?$/.exec(value);
  if (!match) return undefined;
  const start = Number(match[1]);
  const end = match[2] ? Number(match[2]) : start;
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 1 || end < start) {
    return undefined;
  }
  return [start, end];
}
