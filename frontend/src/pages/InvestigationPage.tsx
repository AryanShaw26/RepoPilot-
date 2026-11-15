import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowRight, ClipboardCheck, FileText } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { createPlan } from "../api/plans";
import { getTestRecommendations, getInvestigation } from "../api/investigations";
import { getCapabilities } from "../api/health";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { EvidenceMeter } from "../components/ui/InstrumentWidgets";
import { Panel } from "../components/ui/Panel";
import { Statement } from "../components/ui/Statement";
import { TextArea } from "../components/ui/TextArea";
import { presentApiError } from "../utils/apiErrors";
import { LoadingState, PageHeading, QueryError, StatusBadge, TrustNote } from "./shared";

export function InvestigationPage() {
  const { repositoryId = "", investigationId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [userNotes, setUserNotes] = useState("");
  const investigation = useQuery({
    queryKey: ["investigation", investigationId],
    queryFn: () => getInvestigation(investigationId),
    enabled: Boolean(investigationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "processing" ? 1500 : false;
    },
  });
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: getCapabilities });
  const plan = useMutation({
    mutationFn: () => createPlan(investigationId, userNotes.trim() || undefined),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["investigation", investigationId] });
      navigate(`/repositories/${repositoryId}/plans/${result.id}`);
    },
  });
  const testRecommendations = useMutation({
    mutationFn: () => getTestRecommendations(investigationId),
  });

  if (investigation.isPending) return <LoadingState label="Loading investigation…" />;
  if (investigation.isError) return <QueryError error={investigation.error} onRetry={() => void investigation.refetch()} />;
  const data = investigation.data;

  return (
    <div>
      <PageHeading
        eyebrow="Issue evidence"
        title={data.issue.title || "Investigation"}
        description="Repository facts are separated from AI-generated hypotheses."
        actions={
          <>
            <Badge tone="neutral">Issue title · User supplied</Badge>
            {capabilities.data ? (
              <Badge tone={capabilities.data.llm_available ? "green" : "amber"}>
                {capabilities.data.llm_available ? "AI available · Verified" : "AI unavailable · Verified"}
              </Badge>
            ) : capabilities.isError ? (
              <Badge tone="red">AI capability unverified</Badge>
            ) : null}
            <StatusBadge status={data.status} />
          </>
        }
      />
      {capabilities.data && !capabilities.data.llm_available && (
        <div className="mb-5">
          <TrustNote>AI is unavailable. The investigation uses deterministic evidence-only fallback; no generated hypotheses are expected.</TrustNote>
        </div>
      )}
      {(data.status === "pending" || data.status === "processing") ? (
        <Panel variant="instrument" className="mb-5">
          <div className="flex items-center gap-3">
            <span className="size-3 animate-pulse rounded-full bg-led-amber" aria-hidden="true" />
            <p className="font-mono text-sm">Collecting ranked source evidence…</p>
          </div>
        </Panel>
      ) : null}
      {data.status === "failed" && (
        <div className="mb-5"><QueryError error={new Error(data.error || "Investigation failed.")} /></div>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-5">
          <Panel header={<div className="flex items-center gap-2"><FileText className="size-4 text-ink-muted" /><h2 className="font-display text-xl">Issue report</h2><Badge tone="neutral">User supplied</Badge></div>}>
            {data.issue.url && <a href={data.issue.url} target="_blank" rel="noreferrer" className="break-all font-mono text-xs text-accent underline">{data.issue.url}</a>}
            <p className="mt-3 whitespace-pre-wrap text-sm text-ink-muted">{data.issue.body}</p>
          </Panel>

          <Panel header={<div className="flex items-center justify-between gap-3"><h2 className="font-display text-xl">Ranked evidence</h2><Badge tone="green">{data.results.length} results · Verified</Badge></div>}>
            {data.results.length ? (
              <ol className="space-y-4">
                {data.results.map((result) => (
                  <li key={`${result.rank}-${result.file_path}`} className="rounded-md border border-edge bg-surface-inset p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <Link to={`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(result.file_path)}${result.symbol ? `&line=${result.symbol.start_line}-${result.symbol.end_line}` : ""}`} className="break-all font-mono text-sm text-accent underline">
                          <Statement text={`${result.file_path}${result.symbol ? ` · ${result.symbol.name}` : ""}`} kind="fact" />
                        </Link>
                        {result.symbol && <p className="mt-1 font-mono text-xs text-ink-muted">Lines {result.symbol.start_line}–{result.symbol.end_line} · {result.symbol.kind} · Verified</p>}
                      </div>
                      <Badge tone="blue">Rank {result.rank} · score {result.score.toFixed(3)} · Verified</Badge>
                    </div>
                    <p className="mt-3 text-sm"><Statement text={result.why_relevant.text} kind="hypothesis" /></p>
                    {result.evidence.map((evidence, index) => (
                      <div key={`${evidence.start_line}-${index}`} className="mt-3 rounded border border-edge bg-glass p-3 text-glass-ink">
                        <Link
                          to={`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(result.file_path)}&line=${evidence.start_line}-${evidence.end_line}`}
                          className="mb-1 inline-block font-mono text-[10px] text-glass-ink underline"
                        >
                          Lines {evidence.start_line}–{evidence.end_line} · Verified
                        </Link>
                        <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs leading-6">{evidence.snippet}</pre>
                      </div>
                    ))}
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState title="No evidence results" description="No source evidence was returned for this investigation." />
            )}
          </Panel>

          <Panel header={<div className="flex items-center justify-between gap-3"><h2 className="font-display text-xl">Hypotheses</h2><Badge tone="amber">{data.hypotheses.length} · AI-generated</Badge></div>}>
            {data.hypotheses.length ? (
              <ul className="space-y-3">
                {data.hypotheses.map((hypothesis) => (
                  <li key={hypothesis.id} className="rounded border border-led-amber/40 bg-surface-inset p-3">
                    <Statement text={hypothesis.text} kind="hypothesis" />
                    <p className="mt-2 font-mono text-[10px] text-ink-muted">
                      Confidence: {hypothesis.confidence} · Evidence refs: {hypothesis.evidence_refs.join(", ") || "none"}
                      {hypothesis.unsupported ? " · Unsupported" : ""}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No hypotheses returned" description="This investigation produced no AI-generated hypotheses." />
            )}
          </Panel>

          <Panel header={<h2 className="font-display text-xl">Test recommendations</h2>}>
            {testRecommendations.data ? (
              <div className="space-y-4">
                {testRecommendations.data.existing.length > 0 && (
                  <div>
                    <h3 className="mb-2 font-mono text-xs uppercase text-ink-muted">Existing tests</h3>
                    <ul className="space-y-2">
                      {testRecommendations.data.existing.map((test, index) => (
                        <li key={`${test.path}-${index}`}><Statement text={`${test.path} · ${test.method} · ${test.confidence}`} kind="fact" /></li>
                      ))}
                    </ul>
                  </div>
                )}
                <div>
                  <h3 className="mb-2 font-mono text-xs uppercase text-ink-muted">Suggested scenarios</h3>
                  <ul className="space-y-2">
                    {testRecommendations.data.recommended.map((test, index) => (
                      <li key={`${test.scenario}-${index}`}><Statement text={test.scenario} kind="hypothesis" /></li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <>
                <p className="mb-3 text-sm text-ink-muted">Request suggestions for regression and edge-case tests.</p>
                <Button
                  disabled={testRecommendations.isPending || data.status !== "ready"}
                  onClick={() => testRecommendations.mutate()}
                >
                  <ClipboardCheck className="size-4" /> {testRecommendations.isPending ? "Generating…" : "Suggest tests"}
                </Button>
                {testRecommendations.isError && <p role="alert" className="mt-3 text-sm text-led-red">{presentApiError(testRecommendations.error).message}</p>}
              </>
            )}
          </Panel>
        </div>

        <aside className="space-y-4">
          <EvidenceMeter strength={data.evidence_strength} count={data.results.length} />
          <Panel header={<h2 className="font-display text-xl">Extracted terms</h2>}>
            {Object.entries(data.extracted_terms).map(([category, terms]) => (
              <div key={category} className="mb-3 last:mb-0">
                <p className="font-mono text-[10px] uppercase text-ink-muted">{category} · Verified</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {Array.isArray(terms) && terms.length
                    ? terms.map((term) => <Badge key={String(term)} tone="neutral">{String(term)}</Badge>)
                    : <span className="text-xs text-ink-faint">None</span>}
                </div>
              </div>
            ))}
          </Panel>
          <Panel header={<h2 className="font-display text-xl">Create a plan</h2>}>
            <TextArea
              label="Optional contributor notes"
              value={userNotes}
              onChange={(event) => setUserNotes(event.target.value)}
              maxLength={5000}
              placeholder="Constraints, areas to avoid, or context…"
            />
            {plan.isError && <p role="alert" className="mt-2 text-sm text-led-red">{presentApiError(plan.error).message}</p>}
            <Button
              className="mt-3 w-full"
              variant="primary"
              disabled={plan.isPending || data.status !== "ready"}
              onClick={() => plan.mutate()}
            >
              {plan.isPending ? "Building plan…" : "Create contribution plan"} <ArrowRight className="size-4" />
            </Button>
            <Link to={`/repositories/${repositoryId}/tests`} className="mt-3 inline-block text-xs text-accent underline">View test intelligence</Link>
          </Panel>
          <TrustNote>{data.disclaimer}</TrustNote>
        </aside>
      </div>
    </div>
  );
}
