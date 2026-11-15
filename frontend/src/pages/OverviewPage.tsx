import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, FileCode2, GitBranch, Languages, Star } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getRepositoryOverview } from "../api/repositories";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Panel } from "../components/ui/Panel";
import { StatWell } from "../components/ui/InstrumentWidgets";
import { Statement } from "../components/ui/Statement";
import type { RepositoryOverview } from "../types";
import { LoadingState, PageHeading, QueryError, TrustNote } from "./shared";

export function OverviewPage() {
  const { repositoryId = "" } = useParams();
  const overview = useQuery({
    queryKey: ["repository", repositoryId],
    queryFn: () => getRepositoryOverview(repositoryId),
    enabled: Boolean(repositoryId),
  });

  if (overview.isPending) return <LoadingState label="Loading repository overview…" />;
  if (overview.isError) return <QueryError error={overview.error} onRetry={() => void overview.refetch()} />;

  const repository = overview.data;
  return (
    <div>
      <PageHeading
        eyebrow={`${repository.owner}/${repository.name}`}
        title="Repository overview"
        description="A factual snapshot of indexed repository metadata and structure."
        actions={
          <>
            <Link to={`/repositories/${repositoryId}/explorer`}><Button variant="primary"><FileCode2 className="size-4" /> Explore files</Button></Link>
            <a href={repository.url} target="_blank" rel="noreferrer"><Button variant="ghost">Open on GitHub <ArrowUpRight className="size-4" /></Button></a>
          </>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(17rem,0.6fr)]">
        <div className="space-y-5">
          <Panel variant="instrument">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="font-display text-3xl">{repository.owner}/{repository.name}</h2>
                {repository.description && (
                  <p className="mt-2 max-w-3xl text-sm text-glass-ink/80"><Statement text={repository.description} kind="fact" /></p>
                )}
              </div>
              <Badge tone="green"><span aria-hidden="true">✓</span> Repository metadata · Verified</Badge>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <FactChip icon={<GitBranch className="size-4" />} label="Branch" value={repository.branch} />
              <FactChip icon={<Star className="size-4" />} label="Stars" value={repository.stars?.toLocaleString() ?? "—"} />
              <FactChip icon={<Languages className="size-4" />} label="Languages" value={String(repository.stats?.languages_count ?? Object.keys(repository.languages ?? {}).length)} />
              <FactChip icon={<FileCode2 className="size-4" />} label="Files indexed" value={String(repository.stats?.files_count ?? 0)} />
            </div>
          </Panel>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatWell label="Source files" value={repository.stats?.files_count ?? 0} />
            <StatWell label="Symbols" value={repository.stats?.symbols_count ?? 0} />
            <StatWell label="Test files" value={repository.stats?.tests_count ?? 0} />
            <StatWell label="Languages" value={repository.stats?.languages_count ?? 0} />
          </div>

          <Panel header={<h2 className="font-display text-xl">Languages</h2>}>
            {Object.entries(repository.languages ?? {}).length === 0 ? (
              <EmptyState title="No language data" description="The repository did not provide language metadata." />
            ) : (
              <div className="space-y-3">
                {Object.entries(repository.languages).map(([language, bytes]) => {
                  const total = Object.values(repository.languages).reduce((sum, size) => sum + Number(size), 0);
                  const percent = total > 0 ? (Number(bytes) / total) * 100 : 0;
                  return (
                    <div key={language}>
                      <div className="mb-1 flex justify-between gap-3 text-sm">
                        <Statement text={language} kind="fact" />
                        <span className="font-mono text-xs text-ink-muted">{Number(bytes).toLocaleString()} bytes · Verified</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-pill bg-surface-inset">
                        <div className="h-full rounded-pill bg-accent" style={{ width: `${percent}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>

          <Panel header={<h2 className="font-display text-xl">Entry points</h2>}>
            {repository.entry_points.length ? (
              <ul className="space-y-3">
                {repository.entry_points.map((entry) => (
                  <li key={entry.path} className="rounded border border-edge bg-surface-inset p-3">
                    <Statement text={entry.path} kind="fact" className="font-mono text-sm" />
                    <p className="mt-1 text-xs text-ink-muted">Verified: {entry.reason}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No entry points detected" description="No entry points were reported by the repository analyzer." />
            )}
          </Panel>
        </div>

        <aside className="space-y-5">
          <Panel header={<h2 className="font-display text-xl">Repository metadata</h2>}>
            <dl className="space-y-4 text-sm">
              <MetadataRow label="Default branch" value={repository.branch} />
              <MetadataRow label="Commit" value={repository.commit_sha || "Not recorded"} />
              <MetadataRow label="License" value={repository.license || "Not specified"} />
              <MetadataRow label="Repository size" value={repository.size_kb === null ? "Not reported" : `${repository.size_kb} KB`} />
              <MetadataRow label="Status" value={repository.status} />
            </dl>
            {repository.topics.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {repository.topics.map((topic) => <Badge key={topic} tone="blue">{topic} · Verified</Badge>)}
              </div>
            )}
          </Panel>

          <Panel header={<h2 className="font-display text-xl">Detected frameworks</h2>}>
            {repository.frameworks.length ? (
              <ul className="space-y-3">
                {repository.frameworks.map((framework, index) => (
                  <li key={`${framework.name}-${index}`} className="border-b border-edge pb-3 last:border-0">
                    <Statement text={framework.name} kind="fact" />
                    <p className="mt-1 text-xs text-ink-muted">Evidence: {framework.evidence}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No frameworks detected" description="Framework metadata is not available for this repository." />
            )}
          </Panel>

          {repository.architecture_summary && (
            <Panel header={<h2 className="font-display text-xl">Architecture summary</h2>}>
              <Statement text={repository.architecture_summary} kind="hypothesis" />
              <TrustNote>Generated summary; treat as a hypothesis and verify against source files.</TrustNote>
            </Panel>
          )}

          {repository.readme_excerpt && (
            <Panel header={<h2 className="font-display text-xl">README excerpt</h2>}>
              <Statement text={repository.readme_excerpt} kind="fact" />
            </Panel>
          )}
        </aside>
      </div>
    </div>
  );
}

function FactChip({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded border border-glass-ink/25 bg-glass px-3 py-2 text-glass-ink">
      <div className="flex items-center gap-2 text-glass-ink/70">{icon}<span className="font-mono text-[10px] uppercase">{label}</span></div>
      <p className="mt-1 font-mono text-sm">{value}</p>
      <p className="font-mono text-[10px] text-glass-ink/70">Verified</p>
    </div>
  );
}

function MetadataRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">{label}</dt>
      <dd className="mt-1 break-words text-sm"><Statement text={value} kind="fact" /></dd>
    </div>
  );
}
