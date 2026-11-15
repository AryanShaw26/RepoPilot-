import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Filter, Search as SearchIcon } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getCapabilities } from "../api/health";
import { searchRepository, type SearchFilters } from "../api/search";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Panel } from "../components/ui/Panel";
import { Segmented } from "../components/ui/Segmented";
import { Statement } from "../components/ui/Statement";
import { TextInput } from "../components/ui/TextInput";
import { presentApiError } from "../utils/apiErrors";
import { LoadingState, PageHeading, QueryError, TrustNote } from "./shared";

type SearchMode = "hybrid" | "keyword" | "symbol" | "semantic";

export function SearchPage() {
  const { repositoryId = "" } = useParams();
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [pathPrefix, setPathPrefix] = useState("");
  const [language, setLanguage] = useState("");
  const [excludeTests, setExcludeTests] = useState(false);
  const [requestError, setRequestError] = useState<unknown>(null);
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: getCapabilities });
  const filters: SearchFilters = {
    ...(pathPrefix.trim() ? { path_prefix: pathPrefix.trim() } : {}),
    ...(language.trim() ? { language: language.trim() } : {}),
    exclude_tests: excludeTests,
  };
  const results = useQuery({
    queryKey: ["search", repositoryId, submittedQuery, mode, filters],
    queryFn: () => searchRepository(repositoryId, submittedQuery, mode, 20, filters),
    enabled: Boolean(repositoryId && submittedQuery),
  });

  const handleSearch = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) return;
    setRequestError(null);
    setSubmittedQuery(query.trim());
  };
  const error = requestError ?? (results.isError ? results.error : null);

  return (
    <div>
      <PageHeading
        eyebrow="Code search"
        title="Search the repository"
        description="Find source snippets by keyword, symbol, or hybrid retrieval."
      />

      <Panel className="mb-5">
        <form onSubmit={handleSearch} className="space-y-4">
          <TextInput
            label="Search query"
            placeholder="Function name, error message, or behavior"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            leftElement={<SearchIcon className="size-4" />}
            required
          />
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">Retrieval mode</p>
              <Segmented
                label="Search retrieval mode"
                value={mode}
                onChange={setMode}
                options={[
                  { value: "hybrid", label: "Hybrid" },
                  { value: "keyword", label: "Keyword" },
                  { value: "symbol", label: "Symbol" },
                  ...(capabilities.data?.semantic_search ? [{ value: "semantic" as const, label: "Semantic" }] : []),
                ]}
              />
            </div>
            <Button type="submit" variant="primary" disabled={!query.trim() || results.isFetching}>
              <SearchIcon className="size-4" /> Search
            </Button>
          </div>
          <details className="rounded border border-edge bg-surface-inset p-3">
            <summary className="flex min-h-11 cursor-pointer items-center gap-2 font-mono text-xs text-ink-muted">
              <Filter className="size-4" /> Filters
            </summary>
            <div className="grid gap-3 pt-3 sm:grid-cols-2">
              <TextInput label="Path prefix" placeholder="src/" value={pathPrefix} onChange={(event) => setPathPrefix(event.target.value)} />
              <TextInput label="Language" placeholder="python, typescript…" value={language} onChange={(event) => setLanguage(event.target.value)} />
              <label className="flex min-h-11 items-center gap-2 font-mono text-xs text-ink-muted sm:col-span-2">
                <input type="checkbox" checked={excludeTests} onChange={(event) => setExcludeTests(event.target.checked)} className="size-4 accent-accent" />
                Exclude test files
              </label>
            </div>
          </details>
        </form>
      </Panel>

      {error && <div className="mb-4"><QueryError error={error} onRetry={() => void results.refetch()} /></div>}
      {results.isPending && submittedQuery && <LoadingState label="Searching indexed source…" />}
      {results.data && (
        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-xl">Results for “{submittedQuery}”</h2>
            <div className="flex gap-2">
              <Badge tone="neutral">{results.data.results.length} results · Verified</Badge>
              <Badge tone={results.data.semantic_available ? "green" : "amber"}>
                {results.data.semantic_available ? "Semantic available" : "Keyword/symbol fallback"}
              </Badge>
            </div>
          </div>
          {!results.data.semantic_available && (
            <TrustNote>Semantic retrieval is unavailable for this backend; the selected query is handled by the available search modes.</TrustNote>
          )}
          {results.data.results.length === 0 ? (
            <Panel className="mt-4"><EmptyState title="No matches" description="Try a shorter query or relax the path and language filters." /></Panel>
          ) : (
            <div className="mt-4 space-y-3">
              {results.data.results.map((result, index) => (
                <Panel key={`${result.file_path}-${result.start_line}-${index}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        to={`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(result.file_path)}&line=${result.start_line}-${result.end_line}`}
                        className="break-all font-mono text-sm text-accent underline"
                      >
                        <Statement text={`${result.file_path}:${result.start_line}-${result.end_line}`} kind="fact" />
                      </Link>
                      {result.symbol_name && <p className="mt-1 text-xs text-ink-muted">Symbol: {result.symbol_name} · Verified</p>}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {result.source.map((source) => <Badge key={source} tone="blue">{source} · Verified</Badge>)}
                      <Badge tone="neutral">Score {result.score.toFixed(3)} · Verified</Badge>
                    </div>
                  </div>
                  <pre className="mt-3 overflow-x-auto rounded border border-edge bg-glass p-3 font-mono text-xs leading-6 text-glass-ink">
                    <Statement text={result.snippet} kind="fact" className="whitespace-pre-wrap" />
                  </pre>
                </Panel>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
