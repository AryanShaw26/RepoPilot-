import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, FilePlus2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { createInvestigation, listInvestigations } from "../api/investigations";
import type { CreateInvestigationParams } from "../api/investigations";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Panel } from "../components/ui/Panel";
import { Segmented } from "../components/ui/Segmented";
import { TextArea } from "../components/ui/TextArea";
import { TextInput } from "../components/ui/TextInput";
import { presentApiError } from "../utils/apiErrors";
import { PageHeading, QueryError, StatusBadge } from "./shared";

type IssueSource = "github_issue" | "text";

export function IssuesPage() {
  const { repositoryId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sourceType, setSourceType] = useState<IssueSource>("github_issue");
  const [issueUrl, setIssueUrl] = useState("");
  const [issueTitle, setIssueTitle] = useState("");
  const [issueBody, setIssueBody] = useState("");
  const investigations = useQuery({
    queryKey: ["investigations", repositoryId],
    queryFn: () => listInvestigations(repositoryId),
    enabled: Boolean(repositoryId),
  });
  const create = useMutation({
    mutationFn: (params: CreateInvestigationParams) => createInvestigation(repositoryId, params),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["investigations", repositoryId] });
      navigate(`/repositories/${repositoryId}/investigations/${result.investigation_id}`);
    },
  });

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const params: CreateInvestigationParams = sourceType === "github_issue"
      ? { source_type: "github_issue", issue_url: issueUrl.trim() }
      : { source_type: "text", issue_title: issueTitle.trim(), issue_body: issueBody.trim() };
    create.mutate(params);
  };
  const apiError = create.isError ? presentApiError(create.error) : null;

  return (
    <div>
      <PageHeading
        eyebrow="Issue investigation"
        title="Investigate a problem"
        description="Turn a GitHub issue or a written report into ranked source evidence and explicit hypotheses."
      />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Panel header={<h2 className="font-display text-xl">Start investigation</h2>}>
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">Input source</p>
              <Segmented
                label="Issue input source"
                value={sourceType}
                onChange={setSourceType}
                options={[
                  { value: "github_issue", label: "GitHub issue" },
                  { value: "text", label: "Paste report" },
                ]}
              />
            </div>
            {sourceType === "github_issue" ? (
              <TextInput
                label="GitHub issue URL"
                placeholder="https://github.com/owner/repository/issues/123"
                value={issueUrl}
                onChange={(event) => setIssueUrl(event.target.value)}
                autoComplete="url"
                required
                helperText="The issue must belong to this analyzed repository."
              />
            ) : (
              <>
                <TextInput label="Issue title" value={issueTitle} onChange={(event) => setIssueTitle(event.target.value)} required maxLength={500} />
                <TextArea label="Issue description" value={issueBody} onChange={(event) => setIssueBody(event.target.value)} required maxLength={20000} rows={7} />
              </>
            )}
            {apiError && (
              <div role="alert" className="rounded border border-led-red/50 bg-surface-inset p-3">
                <p className="font-mono text-xs font-semibold text-led-red">{apiError.title} {apiError.code && `· ${apiError.code}`}</p>
                <p className="mt-1 text-sm text-ink-muted">{apiError.message}</p>
              </div>
            )}
            <Button type="submit" variant="primary" disabled={create.isPending}>
              <FilePlus2 className="size-4" /> {create.isPending ? "Starting…" : "Start investigation"}
            </Button>
          </form>
        </Panel>

        <Panel header={<div className="flex items-center justify-between gap-3"><h2 className="font-display text-xl">Recent investigations</h2><Badge tone="neutral">{investigations.data?.length ?? 0} · Verified</Badge></div>}>
          {investigations.isError ? (
            <QueryError error={investigations.error} onRetry={() => void investigations.refetch()} />
          ) : investigations.isPending ? (
            <p role="status" className="text-sm text-ink-muted">Loading investigations…</p>
          ) : investigations.data.length ? (
            <ul className="divide-y divide-edge">
              {investigations.data.map((investigation) => (
                <li key={investigation.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <Link to={`/repositories/${repositoryId}/investigations/${investigation.id}`} className="font-medium hover:text-accent">
                      <span className="mr-2 inline-flex"><Badge tone="green">Verified</Badge></span>
                      {investigation.title || "Untitled investigation"}
                    </Link>
                    <p className="mt-1 font-mono text-[10px] text-ink-muted">{new Date(investigation.created_at).toLocaleString()} · Verified</p>
                  </div>
                  <StatusBadge status={investigation.status} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No investigations yet" description="Create an investigation to locate relevant files and evidence." icon={<ExternalLink className="size-8" />} />
          )}
        </Panel>
      </div>
    </div>
  );
}
