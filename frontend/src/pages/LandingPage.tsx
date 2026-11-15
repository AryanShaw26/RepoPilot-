import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpen, Github, Plus, Search, Trash2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { analyzeRepository, deleteRepository, getRepositories } from "../api/repositories";
import { getCapabilities, getHealth } from "../api/health";
import type { RepositorySummary } from "../types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Dialog } from "../components/ui/Dialog";
import { EmptyState } from "../components/ui/EmptyState";
import { Panel } from "../components/ui/Panel";
import { Statement } from "../components/ui/Statement";
import { TextInput } from "../components/ui/TextInput";
import { PageHeading, QueryError, StatusBadge } from "./shared";
import { presentApiError } from "../utils/apiErrors";

export function LandingPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [formError, setFormError] = useState<unknown>(null);
  const [repositoryToDelete, setRepositoryToDelete] = useState<RepositorySummary | null>(null);
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: getRepositories });
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 15_000 });
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: getCapabilities });
  const canAnalyze = Boolean(health.data?.db && health.data.migrated);
  const analysis = useMutation({
    mutationFn: () => analyzeRepository(url.trim(), branch.trim() || undefined),
    onSuccess: (result) => {
      setFormError(null);
      navigate(`/repositories/${result.repository_id}/analysis`);
    },
    onError: setFormError,
  });
  const removeRepository = useMutation({
    mutationFn: (id: string) => deleteRepository(id),
    onSuccess: () => {
      setRepositoryToDelete(null);
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
    },
  });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    if (!url.trim()) {
      setFormError(new Error("Enter a GitHub repository URL."));
      return;
    }
    analysis.mutate();
  };

  const error = formError ? presentApiError(formError) : null;

  return (
    <div>
      <div className="mb-8 grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(19rem,0.8fr)]">
        <section className="flex flex-col justify-center py-4">
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge tone="blue"><Github className="size-3" /> GitHub repositories</Badge>
            <Badge tone="neutral"><BookOpen className="size-3" /> Evidence-first analysis</Badge>
          </div>
          <h1 className="max-w-3xl font-display text-4xl font-semibold leading-tight sm:text-5xl">
            Understand a repository before you change it.
          </h1>
          <p className="mt-4 max-w-2xl text-base text-ink-muted">
            Map the codebase, trace dependencies, search source, and turn issue reports into evidence-backed plans.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {capabilities.data ? (
              <>
                <Badge tone={capabilities.data.semantic_search ? "green" : "amber"}>
                  {capabilities.data.semantic_search ? "Semantic search available" : "Keyword and symbol search"}
                </Badge>
                <span className="self-center text-xs text-ink-muted">
                  {capabilities.data.semantic_search ? "Capability · Verified" : "Semantic search unavailable · Verified"}
                </span>
              </>
            ) : capabilities.isError ? (
              <Badge tone="red">Search capabilities unavailable</Badge>
            ) : (
              <Badge tone="neutral">Checking search capability…</Badge>
            )}
          </div>
        </section>

        <Panel variant="raised" className="self-center">
          <div className="mb-4 flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-md border border-edge bg-surface-inset text-accent shadow-inset" aria-hidden="true">
              <Plus className="size-5" />
            </span>
            <div>
              <h2 className="font-display text-2xl">Analyze a repository</h2>
              <p className="font-mono text-xs text-ink-muted">Public GitHub repository URL</p>
            </div>
          </div>
          {!canAnalyze && (
            <div role="status" className="mb-4 rounded border border-led-amber/50 bg-surface-inset p-3 text-sm text-ink-muted">
              {health.isError
                ? "The backend API is unreachable. Start the API and try again."
                : "Backend is running but the database isn’t ready. Analysis is paused until it is available."}
            </div>
          )}
          {error && (
            <div role="alert" className="mb-3 rounded border border-led-red/50 bg-surface-inset p-3">
              <p className="font-mono text-xs text-led-red">{error.title}{error.code ? ` · ${error.code}` : ""}</p>
              <p className="mt-1 text-sm text-ink-muted">{error.message}</p>
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-3">
            <TextInput
              label="Repository URL"
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              autoComplete="url"
              required
              helperText="Use the canonical repository URL."
            />
            <TextInput
              label="Branch (optional)"
              placeholder="default branch"
              value={branch}
              onChange={(event) => setBranch(event.target.value)}
            />
            <Button type="submit" variant="primary" className="w-full" disabled={!canAnalyze || analysis.isPending}>
              {analysis.isPending ? "Starting analysis…" : "Analyze repository"}
              {!analysis.isPending && <ArrowRight className="size-4" aria-hidden="true" />}
            </Button>
          </form>
        </Panel>
      </div>

      <section>
        <PageHeading
          eyebrow="Local workspace"
          title="Repositories"
          description="Repositories are scoped to this browser session."
          actions={
            <Link to="/styleguide">
              <Button variant="ghost"><Search className="size-4" /> UI styleguide</Button>
            </Link>
          }
        />
        {repositories.isError ? (
          <QueryError error={repositories.error} onRetry={() => void repositories.refetch()} />
        ) : repositories.isPending ? (
          <div role="status" className="p-4 font-mono text-sm text-ink-muted">Loading repositories…</div>
        ) : repositories.data.length === 0 ? (
          <Panel>
            <EmptyState
              title="No repositories yet"
              description="Add a public GitHub repository above to create a searchable, evidence-linked workspace."
              icon={<Github className="size-8" />}
            />
          </Panel>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {repositories.data.map((repository) => (
              <RepositoryCard
                key={repository.id}
                repository={repository}
                onDelete={() => setRepositoryToDelete(repository)}
              />
            ))}
          </div>
        )}
      </section>

      <Dialog
        open={repositoryToDelete !== null}
        title="Remove repository?"
        onClose={() => setRepositoryToDelete(null)}
      >
        <p className="text-sm text-ink-muted">
          This removes the local analysis for <strong>{repositoryToDelete?.owner}/{repositoryToDelete?.name}</strong>.
        </p>
        {removeRepository.isError && (
          <div className="mt-3"><QueryError error={removeRepository.error} /></div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setRepositoryToDelete(null)}>Cancel</Button>
          <Button
            variant="danger"
            disabled={!repositoryToDelete || removeRepository.isPending}
            onClick={() => repositoryToDelete && removeRepository.mutate(repositoryToDelete.id)}
          >
            <Trash2 className="size-4" /> Remove
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

function RepositoryCard({
  repository,
  onDelete,
}: {
  repository: RepositorySummary;
  onDelete: () => void;
}) {
  return (
    <Panel
      className="flex h-full flex-col"
      header={
        <div className="flex min-w-0 items-center gap-2">
          <Github className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
          <h3 className="truncate font-mono text-sm font-semibold">{repository.owner}/{repository.name}</h3>
        </div>
      }
      footer={
        <div className="flex w-full items-center justify-between gap-2">
          <StatusBadge status={repository.status} />
          <div className="flex gap-1">
            <Link to={`/repositories/${repository.id}`}>
              <Button size="small" variant="primary">Open <ArrowRight className="size-3.5" /></Button>
            </Link>
            <Button size="icon" variant="ghost" aria-label={`Remove ${repository.owner}/${repository.name}`} onClick={onDelete}>
              <Trash2 className="size-4" />
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-2">
        <Statement text={`Branch: ${repository.branch}`} kind="fact" className="text-xs" />
        {repository.description && (
          <Statement text={repository.description} kind="fact" className="line-clamp-2 text-sm text-ink-muted" />
        )}
        {repository.stars !== null && repository.stars !== undefined && (
          <Statement text={`${repository.stars.toLocaleString()} GitHub stars`} kind="fact" className="text-xs" />
        )}
        <Statement text={repository.url} kind="fact" className="truncate font-mono text-[10px] text-ink-faint" />
      </div>
    </Panel>
  );
}
