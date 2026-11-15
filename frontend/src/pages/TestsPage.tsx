import { useQuery } from "@tanstack/react-query";
import { ArrowRight, TestTube2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getTestIntelOverview } from "../api/plans";
import { Badge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { Panel } from "../components/ui/Panel";
import { StatWell } from "../components/ui/InstrumentWidgets";
import { Statement } from "../components/ui/Statement";
import { TrustNote, LoadingState, PageHeading, QueryError } from "./shared";

export function TestsPage() {
  const { repositoryId = "" } = useParams();
  const tests = useQuery({
    queryKey: ["tests", repositoryId],
    queryFn: () => getTestIntelOverview(repositoryId),
    enabled: Boolean(repositoryId),
  });

  if (tests.isPending) return <LoadingState label="Loading test intelligence…" />;
  if (tests.isError) return <QueryError error={tests.error} onRetry={() => void tests.refetch()} />;

  const data = tests.data;
  return (
    <div>
      <PageHeading
        eyebrow="Quality signals"
        title="Test intelligence"
        description="Detected test files and source-to-test mappings. RepoPilot does not run tests."
      />
      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatWell label="Test files detected" value={data.test_files_count} />
        <StatWell label="Source files" value={data.source_files_count} />
        <StatWell label="Mapped source files" value={data.mapped_source_files_count} />
        <div className="rounded-md border border-edge bg-surface-inset p-4 shadow-inset">
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">Coverage proxy</p>
          <p className="mt-1 font-display text-2xl tabular-nums">{data.coverage_proxy_pct.toFixed(1)}%</p>
          <Badge tone="amber" className="mt-2">Proxy · Verified</Badge>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(17rem,0.8fr)]">
        <Panel header={<h2 className="font-display text-xl">Sample test mappings</h2>}>
          {data.sample_mappings.length ? (
            <ul className="divide-y divide-edge">
              {data.sample_mappings.map((mapping, index) => (
                <li key={`${mapping.test_file}-${index}`} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <Statement text={mapping.test_file} kind="fact" className="break-all font-mono text-xs" />
                    <p className="mt-1 text-xs text-ink-muted">Matched by {mapping.method} · Confidence: {mapping.confidence} · Verified</p>
                  </div>
                  <Link to={`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(mapping.test_file)}`} className="shrink-0">
                    <span className="inline-flex min-h-11 items-center gap-1 font-mono text-xs text-accent">
                      Open file <ArrowRight className="size-3.5" />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No sample mappings" description="The analyzer did not find source-to-test mappings for this repository." icon={<TestTube2 className="size-8" />} />
          )}
        </Panel>
        <div className="space-y-5">
          <Panel header={<h2 className="font-display text-xl">Detected frameworks</h2>}>
            {data.detected_frameworks.length ? (
              <ul className="flex flex-wrap gap-2">
                {data.detected_frameworks.map((framework) => <li key={framework}><Badge tone="blue">{framework} · Verified</Badge></li>)}
              </ul>
            ) : (
              <p className="text-sm text-ink-muted">No test framework detected.</p>
            )}
          </Panel>
          <TrustNote>{data.disclaimer}</TrustNote>
        </div>
      </div>
    </div>
  );
}
