import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, RotateCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getCapabilities } from "../api/health";
import { getLatestJob, getRepositoryOverview, reanalyseRepository } from "../api/repositories";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { CounterDrum, StageLamps } from "../components/ui/InstrumentWidgets";
import { Panel } from "../components/ui/Panel";
import { presentApiError } from "../utils/apiErrors";
import { LoadingState, PageHeading, QueryError, StatusBadge, TrustNote } from "./shared";

export function AnalysisPage() {
  const { repositoryId = "" } = useParams();
  const queryClient = useQueryClient();
  const job = useQuery({
    queryKey: ["job", repositoryId],
    queryFn: () => getLatestJob(repositoryId),
    enabled: Boolean(repositoryId),
    refetchInterval: (query) => {
      const stage = query.state.data?.stage;
      return stage === "ready" || stage === "failed" ? false : 1000;
    },
  });
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: getCapabilities });
  const overview = useQuery({
    queryKey: ["repository", repositoryId],
    queryFn: () => getRepositoryOverview(repositoryId),
    enabled: job.data?.stage === "ready",
  });
  const reanalyse = useMutation({
    mutationFn: () => reanalyseRepository(repositoryId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["job", repositoryId] }),
  });

  if (job.isPending) return <LoadingState label="Connecting to the analysis job…" />;
  if (job.isError) return <QueryError error={job.error} onRetry={() => void job.refetch()} />;
  const currentJob = job.data;
  const isFailed = currentJob.stage === "failed";
  const isReady = currentJob.stage === "ready";

  return (
    <div>
      <PageHeading
        eyebrow="Analysis cockpit"
        title={isReady ? "Analysis complete" : isFailed ? "Analysis stopped" : "Analyzing repository"}
        description="Live job progress from the repository analysis service."
        actions={<StatusBadge status={isFailed ? "failed" : isReady ? "ready" : "processing"} />}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
        <Panel variant="instrument" className="space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-glass-ink/70">Current stage</p>
              <h2 className="mt-1 font-display text-3xl">{currentJob.stage}</h2>
              <p className="mt-2 text-sm text-glass-ink/80">{currentJob.message || "Waiting for worker progress."}</p>
            </div>
            <div className="rounded border border-glass-ink/30 px-3 py-2 text-right">
              <p className="font-mono text-[10px] uppercase text-glass-ink/70">Progress</p>
              <p className="font-mono text-3xl tabular-nums">{currentJob.progress}%</p>
              <p className="font-mono text-[10px] text-glass-ink/70">Verified job state</p>
            </div>
          </div>

          <div
            role="progressbar"
            aria-label="Repository analysis progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={currentJob.progress}
            className="h-3 overflow-hidden rounded-pill border border-glass-ink/30 bg-glass"
          >
            <div className="h-full rounded-pill bg-accent transition-[width] duration-500" style={{ width: `${currentJob.progress}%` }} />
          </div>

          <StageLamps
            stage={currentJob.stage}
            semanticAvailable={capabilities.data?.semantic_search ?? false}
          />

          {isFailed && (
            <div role="alert" className="rounded border border-led-red/60 bg-led-red/10 p-4">
              <p className="font-mono text-xs font-semibold uppercase text-led-red">Analysis failed</p>
              <p className="mt-1 text-sm">{currentJob.error || "The worker did not provide an error message."}</p>
            </div>
          )}

          {isReady && (
            <div className="flex flex-wrap gap-2">
              <Link to={`/repositories/${repositoryId}`}><Button variant="primary">Open overview <ArrowRight className="size-4" /></Button></Link>
              <Link to={`/repositories/${repositoryId}/explorer`}><Button>Explore source</Button></Link>
            </div>
          )}

          {isFailed && (
            <Button
              variant="primary"
              disabled={reanalyse.isPending}
              onClick={() => reanalyse.mutate()}
            >
              <RotateCw className="size-4" /> Retry analysis
            </Button>
          )}
          {reanalyse.isError && <p role="alert" className="text-sm text-led-red">{presentApiError(reanalyse.error).message}</p>}
        </Panel>

        <div className="space-y-4">
          <CounterDrum value={overview.data?.stats?.files_count ?? null} label="Indexed files" />
          <Panel>
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-display text-xl">Job record</h2>
              <Badge tone={isReady ? "green" : isFailed ? "red" : "amber"}>
                <span aria-hidden="true">{isReady ? "✓" : isFailed ? "!" : "●"}</span>
                {isReady ? "Verified" : isFailed ? "Failed" : "Live"}
              </Badge>
            </div>
            <dl className="mt-4 space-y-3 font-mono text-xs">
              <div className="flex justify-between gap-3"><dt className="text-ink-muted">Job ID</dt><dd className="break-all text-right">{currentJob.id}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-ink-muted">Started</dt><dd>{currentJob.started_at ? `${new Date(currentJob.started_at).toLocaleString()} · Verified` : "Not started"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-ink-muted">Created</dt><dd>{new Date(currentJob.created_at).toLocaleString()} · Verified</dd></div>
            </dl>
          </Panel>
          <TrustNote>
            Analysis status and counts come from the backend. A file count remains unavailable until the overview returns it.
          </TrustNote>
        </div>
      </div>
    </div>
  );
}
